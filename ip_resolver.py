import re

import requests
from requests import Timeout


class IpResolverError(Exception):
    """IpResolver Exceptions"""
    pass


class IpResolver:
    """IP resolver.


    Parse the IP from a website containing plain text, or web page with a single IP.
    """

    def __init__(self, url, alt_url=None):
        """IP resolver.

        Parse the IP from a website containing plain text, or web page with a single IP.

        :param str url: The resolver URL.
        :param str alt_url: Alternative resolver URL.
        """

        self.url = url
        self.alt_url = alt_url

    def resolve_ip(self):
        """Resolve the IP by parsing the content of the resolver URL.

        :return: The resolved IP.
        :rtype: str
        """

        r = None
        try:
            r = requests.get(self.url, timeout=30.0)

            if not r.ok:
                if self.alt_url:
                    print("Main resolver returned and error code HTTP/%s, trying alternate resolver." % str(r.status_code))
                    r = None
                else:
                    raise IpResolverError("IP resolver returned an error code HTTP/%s." % str(r.status_code))

        except Timeout:
            if self.alt_url:
                print("Main resolver timeout, trying alternate resolver.")
            else:
                raise IpResolverError("IP resolver timeout.")

        if r is None and self.alt_url:
            try:
                r = requests.get(self.alt_url, timeout=30.0)

                if not r.ok:
                    raise IpResolverError("Alternate IP resolver returned an error code HTTP/%s." % str(r.status_code))

            except Timeout:
                raise IpResolverError("Alternate IP resolver timeout.")

        if not r.content:
            raise IpResolverError("Invalid content returned by IP resolver.")

        match = re.search("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", r.text)

        if not match:
            raise IpResolverError("IP not found in resolver content.")

        ip = match.group(1)

        return ip
