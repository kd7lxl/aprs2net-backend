
"""
Config download manager. Downloads JSON server configurations from the portal
and maintains current list of servers in the Redis database.

Runs a maintenance thread, so that these operations won't block the polling
operations, even if the portal would be down.
"""

import requests
import json
import threading
import time

POLL_INTERVAL = 2*60

# this is a set of servers to poll, for testing purposes, just to get us started.
test_setup = {
    'T2FINLAND': {
        'host': 'finland',
        'ip4': '85.188.1.32',
        'ip6': '2001:67c:15c:1::32'
    },
    'T2BRAZIL': {
        'host': 'brazil',
        'ip4': '75.144.65.121'
    },
    'T2HAM': {
        'host': 'amsterdam',
        'ip4': '195.90.121.18',
        'ip6': '2a01:348::4:0:34:1:1'
    },
    'T2APRSNZ': {
        'host': 'aprsnz',
        'ip4': '125.236.199.246'
    },
    'T2ARK': {
        'host': 'arkansas',
        'ip4': '67.14.192.41'
    },
    'T2AUSTRIA': {
        'host': 'austria',
        'ip4': '194.208.144.169'
    },
    'T2BASEL': {
        'host': 'basel',
        'ip4': '185.14.156.135',
        'ip6': '2a03:b240:100::1'
    },
    'T2BC': {
        'host': 'bc',
        'ip4': '206.12.104.10'
    },
    'T2BELGIUM': {
        'host': 'belgium',
        'ip4': '193.190.240.225'
    }
}

class ConfigManager:
    def __init__(self, log, red):
        self.log = log
        self.red = red
        
        self.rhead = {'User-agent': 'aprs2net-ConfigManager/2.0'}
        self.http_timeout = 30
        
        self.portal_base_url = 'https://home.tomh.us:8001'
        self.portal_servers_url = '%s/sysop/servers.json' % self.portal_base_url
        self.portal_rotates_url = '%s/sysop/rotates.json' % self.portal_base_url
        
        self.shutdown = False
        
        self.cfg_thread = threading.Thread(target=self.cfg_loop)
        self.cfg_thread.daemon = True
        self.cfg_thread.start()
        
        self.log.info("ConfigManager initialized")
    
    def cfg_loop(self):
        """
        Main configuration thread loop.
        """
        
        while not self.shutdown:
            # Make sure the configuration manager thread does not die
            # permanently due to a spurious error.
            try:
                self.refresh_config()
            except Exception as e:
                self.log.error("ConfigManager refresh_config crashed: %r", e)
                
            time.sleep(POLL_INTERVAL)
    
    def refresh_config(self):
        """
        Fetch configuration from the portal
        """
        self.log.info("Fetching current server list from portal...")
        
        t_start = time.time()
        try:
            r = requests.get(self.portal_servers_url, headers=self.rhead, timeout=self.http_timeout)
            r.raise_for_status()
        except Exception as e:
            self.log.info("Portal: %s - Connection error: %r", self.portal_servers_url, e)
            return False
            
        t_end = time.time()
        t_dur = t_end - t_start
        
        if r.status_code != 200:
            self.log.error("Portal: %s - Failed download, code: %r", self.portal_servers_url, r.status_code)
            return False
        
        d = r.content
        
        try:
            j = json.loads(d)
        except Exception as e:
            self.log.error("Portal: servers.json parsing failed: %r", e)
            return False
        
    def test_load(self, set):
        """
        Load a set of servers in Redis for testing
        """
        
        self.log.info("Loading test set...")
        for i in test_setup.keys():
            self.log.info(" ... %r", i)
            s = test_setup[i]
            s['id'] = i
            
            self.red.storeServer(s)
            if i == 'T2BRAZIL':
                self.red.setPollQ(i, 0)
            else:
                self.red.setPollQ(i, int(time.time()))
    