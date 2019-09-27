import argparse
import configparser
import json
import os
import sys
import re
from configparser import ConfigParser
from datetime import datetime

from ip_resolver import IpResolver, IpResolverError

from livedns_client import LiveDNSClient

config = {}  # type: ConfigParser


def parse_options():
    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--conf", default="config.ini", help="Configuration file.")
    parser.add_argument("--debug", action="store_true", help="Debug mode.")
    parser.add_argument("--dry-run", action="store_true", help="Display information and quit without modifications.")
    parser.add_argument("-l", "--log", default="ip.log", help="Log file.")
    parser.add_argument("-o", "--out", default="ip.txt", help="IP output file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Display more information.")

    return parser.parse_args()


def parse_configuration(conf_file):
    """Parse configuration file."""

    if not os.path.exists(conf_file):
        if conf_file == "config.ini":
            raise RuntimeError("Configuration file not found. Copy the content of config.ini-dist to config.ini and complete the configuration.")
        else:
            raise RuntimeError("Configuration file %s not found." % conf_file)

    global config

    config = configparser.ConfigParser()
    config.read(conf_file)


def livedns_handle(domain, ip, records, debug, dry_run):
    """Query LiveDNS API.

    :param str domain: The domain to handle.
    :param str ip: The current ip.
    :param list[dict[str,str]] records: The records to update.
    :param bool debug: Debug mode.
    :param bool dry_run: Display information and quit without modifications.
    :return: The query result, tuple of action taken and message.
    :rtype: tuple(str,str)
    """

    # init
    ldns = LiveDNSClient(url=config['api']['url'], key=config['api']['key'], debug=debug)

    # check domain
    r_domain = ldns.get_domain(domain)
    if not r_domain:
        raise RuntimeWarning("The domain %s does not exist." % domain)

    # get DNS IP
    r_record = ldns.get_domain_record(domain, record_name=records[0]['name'], record_type=records[0]['type'])
    if not r_record or not r_record.get('values', []):
        raise RuntimeWarning("Main record not found to check DNS IP for domain %s." % domain)

    dns_ip = r_record['values'][0]
    message = "Local IP: %s, DNS IP: %s" % (ip, dns_ip)

    # Dry run
    if dry_run:
        records_map = ldns.get_domain_records_map(domain)

        print("======== Dry run ========")
        if ip == dns_ip:
            print("# Would not update records (no differences):")
        else:
            print("Would update records:")

        for rec in records:
            rec_key = "%s/%s" % (rec['name'], rec['type'])
            print("  %s from %s to %s" % (rec_key, records_map.get(rec_key, None), ip))
        print("=========================")

        return "DRY RUN", message

    # compare IPs
    if ip == dns_ip:
        return "OK", message

    # post snapshot
    r_snap = ldns.post_domain_snapshot(domain, name="dyn-gandi snapshot")
    if r_snap is None:
        raise RuntimeWarning("Could not create snapshot." % domain)

    snapshot_uuid = r_snap['uuid']

    if options.verbose:
        print("Backup snapshot created, uuid: %s." % snapshot_uuid)

    # update DNS records
    for rec in records:
        try:
            r_update = ldns.put_domain_record(domain=domain, record_name=rec['name'], record_type=rec['type'], value=ip, ttl=int(config['dns']['ttl']))
            if r_update is None:
                message = "%s, Error when updating: %s/%s. Backup snapshot uuid: %s." % (message, rec['name'], rec['type'], snapshot_uuid)
                return "ERROR", message

            if options.verbose:
                print("Updated record %s/%s from %s to %s" % (rec['name'], rec['type'], dns_ip, ip))
                print("API response: %s" % json.dumps(r_update, indent=2))
        except Exception as e:
            print("%s, Error: %s. Backup snapshot uuid: %s." % (message, repr(e), snapshot_uuid))
            raise e

    # delete snapshot
    ldns.delete_domain_snapshot(domain, uuid=snapshot_uuid)
    if options.verbose:
        print("Backup snapshot deleted.")

    return "UPDATE", message


def main():
    """Main method."""

    # Init environment
    options = parse_options()
    parse_configuration(options.conf)
    today = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

    # Parse IP
    try:
        ip_resolver = IpResolver(url=config['ip']['resolver_url'], alt_url=config['ip'].get('resolver_url_alt', None))
        ip = ip_resolver.resolve_ip()
    except IpResolverError as e:
        print("%s - %s [ERROR]" % (today, str(e)))
        raise RuntimeWarning("IP resolver returned an error: %s" % str(e))

    if options.verbose:
        print("Resolved IP: %s" % ip)

    # Write IP file output
    if options.out:
        file_ip = None
        if os.path.exists(options.out):
            with open(options.out, 'r') as file:
                file_ip = file.readline().strip()

        if ip != file_ip:
            with open(options.out, 'w') as file:
                file.write(ip)
                file.write("\n")

                if options.verbose:
                    print("Wrote %s to %s file." % (ip, options.out))

    # Query LiveDNS API
    domain = config['dns']['domain']  # type: str

    # Sub-domain check
    domain = domain.replace(".co.uk", ".co_uk")
    if re.match(r"^.+\.[^.]+\.[^.]+$", domain):
        if options.verbose:
            print("Warning: removing sub-domain part of %s" % domain)
        domain = re.sub(r"^.+\.([^.]+\.[^.]+)$", r"\g<1>", domain)
    domain = domain.replace(".co_uk", ".co.uk")

    if options.verbose:
        print("Domain: %s" % domain)

    records = []
    for rec in config['dns']['records'].split(","):
        records.append({"type": "A", "name": rec})

    if not records:
        raise RuntimeWarning("No records to update, check configuration.")

    if options.verbose:
        print("Records: %s" % ", ".join(map(lambda x: "%s/%s" %(x['name'], x['type']), records)))

    try:
        action, message = livedns_handle(
            domain=domain,
            ip=ip,
            records=records,
            debug=options.debug,
            dry_run=options.dry_run
        )
    except Exception as e:
        action, message = "ERROR", "LiveDNS error: %s" % str(e)
        to_log(message, action, datetime_label=today, dump=True, log_file=options.log)

    # output log
    if options.verbose:
        print("")

    to_log(message, action, datetime_label=today, dump=True, log_file=options.log)


def to_log(message, action, datetime_label=None, dump=False, log_file=None):
    """Log to file.

    :param str message: The log message.
    :param str action: The log action.
    :param str datetime_label: The date and time label. ``(default: today)``
    :param bool dump: Dump the log line to stdout.
    """

    if datetime_label is None:
        datetime_label = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

    log_line = "%s - %s [%s]" % (datetime_label, message, action)

    if dump:
        print(log_line)

    if log_file:
        mode = 'a'
        if not os.path.exists(log_file):
            mode = 'x'

        with open(log_file, mode=mode) as file:
            file.write(log_line)
            file.write("\n")


def cli():
    """Command-line interface"""

    try:
        main()
    except RuntimeWarning as w:
        print("  Warning: %s" % w, file=sys.stderr)
        sys.exit(1)


# main entry point
if __name__ == '__main__':
    cli()
