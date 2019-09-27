"""Gandi LiveDNS API to update DNS records with a dynamic IP.

Usage: dyn_gandi [--help] [--verbose] [--dry-run] [--conf=<c>] [--log=<l>] [--out=<o>] [options]...

Options:
  -c --conf=<c>         Configuration file. [default: config.ini].
  -d --debug            Debug mode.
  --dry-run             Display information and quit without modifications.
  -h --help             Display this help and exit.
  -l --log=<l>          Log file. [default: ip.log]
  -o --out=<o>          IP output file. [default: ip.txt]
  -v --verbose          Display more information.

"""
import configparser
import json
import os
import sys
import re
from configparser import ConfigParser
from datetime import datetime

import docopt as docpt
from docopt import docopt
from ip_resolver import IpResolver, IpResolverError

# options
from livedns_client import LiveDNSClient

options = None  # type: dict
debug = False  # type: bool
dry_run = False  # type: bool
verbose = False  # type: bool
conf_file = None  # type: str
log_file = None  # type: str
out_file = None  # type: str

# variables
config = {}  # type: ConfigParser


def parse_options():
    """Parse docopt options and arguments."""

    # options
    global debug, verbose, dry_run, conf_file, log_file, out_file
    debug, verbose, dry_run = options['--debug'], options['--verbose'], options['--dry-run']  # type: bool, bool, bool
    conf_file, log_file, out_file = options['--conf'], options['--log'], options['--out']  # type: str, str, str

    if debug or dry_run:
        verbose = True


def parse_configuration():
    """Parse configuration file."""

    if not os.path.exists(conf_file):
        if conf_file == "config.ini":
            raise RuntimeError("Configuration file not found. Copy the content of config.ini-dist to config.ini and complete the configuration.")
        else:
            raise RuntimeError("Configuration file %s not found." % conf_file)

    global config

    config = configparser.ConfigParser()
    config.read(conf_file)


def livedns_handle(domain, ip, records):
    """Query LiveDNS API.

    :param str domain: The domain to handle.
    :param str ip: The current ip.
    :param list[dict[str,str]] records: The records to update.
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

    if verbose:
        print("Backup snapshot created, uuid: %s." % snapshot_uuid)

    # update DNS records
    for rec in records:
        try:
            r_update = ldns.put_domain_record(domain=domain, record_name=rec['name'], record_type=rec['type'], value=ip, ttl=int(config['dns']['ttl']))
        except Exception as e:
            print(
                "%s, Error: %s. Backup snapshot uuid: %s."
                % (message, repr(e), snapshot_uuid),
                file=sys.stderr,
            )
            raise e

        if r_update is None:
            message = "%s, Error when updating: %s/%s. Backup snapshot uuid: %s." % (message, rec['name'], rec['type'], snapshot_uuid)
            return "ERROR", message

        if verbose:
            print("Updated record %s/%s from %s to %s" % (rec['name'], rec['type'], dns_ip, ip))
            print("API response: %s" % json.dumps(r_update, indent=2))

    # delete snapshot
    ldns.delete_domain_snapshot(domain, uuid=snapshot_uuid)
    if verbose:
        print("Backup snapshot deleted.")

    return "UPDATE", message


def main():
    """Main method."""

    # Init environment
    parse_options()
    parse_configuration()
    today = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

    # Parse IP
    try:
        ip_resolver = IpResolver(url=config['ip']['resolver_url'], alt_url=config['ip'].get('resolver_url_alt', None))
        ip = ip_resolver.resolve_ip()
    except IpResolverError as e:
        print("%s - %s [ERROR]" % (today, str(e)), file=sys.stderr)
        raise RuntimeWarning("IP resolver returned an error: %s" % str(e))

    if verbose:
        print("Resolved IP: %s" % ip)

    # Write IP file output
    if out_file:
        file_ip = None
        if os.path.exists(out_file):
            with open(out_file, 'r') as file:
                file_ip = file.readline().strip()

        if ip != file_ip:
            with open(out_file, 'w') as file:
                file.write(ip)
                file.write("\n")

                if verbose:
                    print("Wrote %s to %s file." % (ip, out_file))

    # Query LiveDNS API
    domain = config['dns']['domain']  # type: str

    # Sub-domain check
    domain = domain.replace(".co.uk", ".co_uk")
    if re.match(r"^.+\.[^.]+\.[^.]+$", domain):
        if verbose:
            print("Warning: removing sub-domain part of %s" % domain)
        domain = re.sub(r"^.+\.([^.]+\.[^.]+)$", r"\g<1>", domain)
    domain = domain.replace(".co_uk", ".co.uk")

    if verbose:
        print("Domain: %s" % domain)

    records = []
    for rec in config['dns']['records'].split(","):
        records.append({"type": "A", "name": rec})

    if not records:
        raise RuntimeWarning("No records to update, check configuration.")

    if verbose:
        print("Records: %s" % ", ".join(map(lambda x: "%s/%s" %(x['name'], x['type']), records)))

    try:
        action, message = livedns_handle(domain=domain, ip=ip, records=records)
    except Exception as e:
        action, message = "ERROR", "LiveDNS error: %s" % str(e)
        to_log(message, action, datetime_label=today, dump=True)

    # output log
    if verbose:
        print()

    to_log(message, action, datetime_label=today, dump=True)


def to_log(message, action, datetime_label=None, dump=False):
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

    global options
    options = docopt(__doc__)
    try:
        main()
    except RuntimeWarning as w:
        print("  Warning: %s" % w, file=sys.stderr)
        sys.exit(1)
    except RuntimeError as w:
        print("%s" % w, file=sys.stderr)
        print(docpt.printable_usage(__doc__))
        sys.exit(1)


# main entry point
if __name__ == '__main__':
    cli()
