import json
import re
import urllib.parse

import requests
from requests import Timeout


class LiveDNSClient:
    """Gandi LiveDNS API client."""

    def __init__(self, url, key, debug=False):
        """Gandi LiveDNS API client.

        :param str url: The API url.
        :param str key: The API key.
        :param bool debug: Debug flag.
        """
        self.url = url
        self.key = key
        self.debug = debug

    def _query_api(self, method, query, json_data=None):
        """Query LiveDNS API.

        :param str method: The REST API method.
        :param str query: The URL query.
        :param dict json_data: Optional JSON data.
        :return: The request JSON response, or ``None`` on error.
        :rtype: dict|list|None
        """

        # parameters
        if not self.url.endswith("/") and not query.startswith("/"):
            query = "/%s" % query

        url = "%s%s" % (self.url, urllib.parse.quote(query))

        headers = {
            "x-api-key":        self.key,
            "Authorization":    "Apikey %s" % self.key,
            "Accept":           "application/json",
        }

        if json_data:
            headers['Content-type'] = "application/json"

        if self.debug:
            print("Requests: method=%s url=%s headers=%s json=%s" % (method, url, headers, json_data))

        # request
        try:
            r = requests.request(method=method, url=url, headers=headers, json=json_data, timeout=60.0)
        except Timeout:
            if self.debug:
                print("Timeout error.")
            return None

        if self.debug:
            print("Response: status_code=%s ok=%s" % (r.status_code, r.ok))

        if not r.ok:
            return None

        if r.status_code == 204:  # HTTP/204 No content (on success)
            return {"code": 204, "message": "ok"}

        # parse response
        r_json = json.loads(re.sub('"rrset_', '"', r.text))  # shorten 'rrset_*' keys
        return r_json

    def get_domains(self):
        """GET domains.

        :return: The domains, or ``None`` on error.
        :rtype: dict|list|None
        """

        return self._query_api(method="GET", query="domains")

    def get_domain(self, domain):
        """GET a domain.

        :param str domain: The domain.
        :return: The domain details, or ``None`` on error.
        :rtype: dict|list|None
        """

        return self._query_api(method="GET", query="domains/%s" % domain)

    def get_domain_records(self, domain):
        """GET domain records.

        :param str domain: The domain.
        :return: The domain records, or ``None`` on error.
        :rtype: dict|list|None
        """
        return self._query_api(method="GET", query="domains/%s/records" % domain)

    def get_domain_records_map(self, domain):
        """GET domain records IP map.

        :param str domain: The domain.
        :return: The domain records IP map by record type/name, or ``None`` on error.
        :rtype: dict[str,str]|None
        """

        records = self.get_domain_records(domain)
        ret = {}
        if not records:
            return None

        for r in records:
            ret["%s/%s" % (r['name'], r['type'])] = ",".join(r['values'])

        return ret

    def get_domain_record(self, domain, record_name, record_type):
        """GET a domain record.

        :param str domain: The domain.
        :param str record_name: The record name.
        :param str record_type: The record type.
        :return: The domain record details, or ``None`` on error.
        :rtype: dict|list|None
        """

        return self._query_api(method="GET", query="domains/%s/records/%s/%s" % (domain, record_name, record_type))

    def post_domain_record(self, domain, record_name, record_type, value, ttl=3600):
        """POST a domain record.

        :param str domain: The domain.
        :param str record_name: The record name.
        :param str record_type: The record type.
        :param str|list[str] value: The record value(s).
        :param int ttl: The record time to live. ``(default: 3600)``
        :return: The API response, or ``None`` on error.
        :rtype: dict|list|None
        """

        if type(value) == str:
            value = [value]

        json_data = {
            "rrset_ttl":        ttl,
            "rrset_values":     value,
        }
        return self._query_api(method="POST", query="domains/%s/records/%s/%s" % (domain, record_name, record_type), json_data=json_data)

    def put_domain_record(self, domain, record_name, record_type, value, ttl=3600):
        """PUT a domain record.

        :param str domain: The domain.
        :param str record_name: The record name.
        :param str record_type: The record type.
        :param str|list[str] value: The record value(s).
        :param int ttl: The record time to live. ``(default: 3600)``
        :return: The API response, or ``None`` on error.
        :rtype: dict|list|None
        """

        if type(value) == str:
            value = [value]

        json_data = {
            "rrset_ttl":        ttl,
            "rrset_values":     value,
        }
        return self._query_api(method="PUT", query="domains/%s/records/%s/%s" % (domain, record_name, record_type), json_data=json_data)

    def delete_domain_record(self, domain, record_name, record_type):
        """DELETE a domain record.

        :param str domain: The domain.
        :param str record_name: The record name.
        :param str record_type: The record type.
        :return: The API response, or ``None`` on error.
        :rtype: dict|list|None
        """

        return self._query_api(method="DELETE", query="domains/%s/records/%s/%s" % (domain, record_name, record_type))

    def get_domain_snapshots(self, domain):
        """GET a domain snapshots.

        :param str domain: The domain.
        :return: The domain snapshots, or ``None`` on error.
        :rtype: dict|list|None
        """

        return self._query_api(method="GET", query="domains/%s/snapshots" % domain)

    def post_domain_snapshot(self, domain, name=None):
        """POST a domain snapshot.

        :param str domain: The domain.
        :param str name: The snapshot name. ``(optional)``
        :return: The API response, or ``None`` on error.
        :rtype: dict|list|None
        """

        json_data = {
            "name":             name,
        }
        return self._query_api(method="POST", query="domains/%s/snapshots" % domain, json_data=json_data)

    def delete_domain_snapshot(self, domain, sid):
        """POST a domain snapshot.

        :param str domain: The domain.
        :param str sid: The snapshot id.
        :return: The API response, or ``None`` on error.
        :rtype: dict|list|None
        """

        return self._query_api(method="DELETE", query="domains/%s/snapshots/%s" % (domain, sid))
