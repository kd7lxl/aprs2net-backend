#!/usr/bin/python

import time
import logging
import logging.config
import ConfigParser
import sys
import os

import aprs2_config

# All configuration variables need to be strings originally.
CONFIG_SECTION = 'nagios'
DEFAULT_CONF = {
    # Server polling interval
    'poll_interval': '120',
    
    # Portal URL for downloading configs
    'portal_servers_url': 'https://portal-url.example.com/blah',
}

class NagiosDriver:
    """
    aprs2.net nagios configuration driver
    """
    def __init__(self, config_file='poller.conf'):
        # read logging config file
        logging.config.fileConfig(config_file)
        logging.Formatter.converter = time.gmtime
        
        self.log = logging.getLogger('nagios')
        self.log.info("Starting up")
        
        # read configuration
        self.config = ConfigParser.ConfigParser()
        self.config.add_section(CONFIG_SECTION)
        
        for option, value in DEFAULT_CONF.iteritems():
            self.config.set(CONFIG_SECTION, option, value)
            
        self.config.read(config_file)
        
        self.poll_interval = self.config.getint(CONFIG_SECTION, 'poll_interval')
        
        self.client_key = self.config.get(CONFIG_SECTION, 'client_key')
        self.client_cert = self.config.get(CONFIG_SECTION, 'client_cert')
        
        self.write_nagios_config = self.config.get(CONFIG_SECTION, 'write_nagios_config')
        
        self.config_etag = None
        self.config_manager = aprs2_config.ConfigManager(logging.getLogger('config'),
        	None,
        	self.config.get(CONFIG_SECTION, 'portal_servers_url'),
        	None,
        	None,
        	credentials = (self.client_cert, self.client_key))
        
    def poll(self):
        """
        Do a single polling round
        """
        
        self.log.info("Fetching current server list from portal...")
        
        j, new_etag = self.config_manager.fetch_config(self.config_manager.portal_servers_url, self.config_etag)
        if j == False:
            return False
        
        self.config_manager.config_etag = new_etag # no need to get this one again
        
        self.process_config(j)
    
    def process_config(self, conf):
    	"""
    	Update nagios config
    	"""
    	
    	host_defs = []
    	ids = []
    	alert_recipients = {}
    	
    	for id in conf:
    	    print "id: %s" % id
    	    s = conf.get(id)
    	    ipv4 = s.get('ipv4')
    	    if ipv4 == None:
    	        continue
    	    
    	    if s.get('email_alerts'):
    	        em = s.get('email')
    	        if em:
    	            alert_recipients[id] = (em)
    	    
    	    s = "define host {\n" \
    	    	+ "    use t2server-host\n" \
    	    	+ "    host_name %s\n" \
    	    	+ "    address %s\n" \
    	    	+ "}\n"
    	    s = s % (id, ipv4)
    	    
    	    host_defs.append(s)
    	    ids.append(id)
    	
    	s = "define hostgroup {\n" \
    	  + "    hostgroup_name t2-servers\n" \
    	  + "    alias T2 servers\n" \
    	  + "    members %s\n" \
    	  + "}\n"
    	
    	host_defs.append(s % ",".join(ids))
    	
    	self.write_out(host_defs, alert_recipients)
        
    def write_out(self, host_defs, alert_recipients):
        """
        Write a nagios configuration
        """
        
        tmpf = "%s.tmp" % self.write_nagios_config
        
        try:
            f = open(tmpf, 'w+')
            f.write("\n".join(host_defs))
            f.close()
        except IOError:
            self.log.error("Failed to write to %s", tmpf)
            return
        
        try:
            os.rename(tmpf, self.write_nagios_config)
        except IOError:
            self.log.error("Failed to rename %s to %s", tmpf, self.write_nagios_config)
            return
        
        
    def loop(self):
        """
        Main Nagios driver loop
        """
        
        while True:
            self.poll()
            time.sleep(self.poll_interval)


cfgfile = 'poller.conf'
if len(sys.argv) > 1:
    cfgfile = sys.argv[1]

driver = NagiosDriver(cfgfile)
driver.loop()
