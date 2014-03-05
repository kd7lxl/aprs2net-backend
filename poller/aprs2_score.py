
def dur_str(i):
    s = ''
    
    if i >= 86400:
        d = i / 86400
        i -= d * 86400
        s += '%dd' % d
        
    if i >= 3600:
        d = i / 3600
        i -= d * 3600
        s += '%dh' % d
        
    if i >= 60:
        d = i / 60
        i -= d * 60
        s += '%dm' % d
        
    if i > 0 or s == '':
        s += '%.0fs' % i
    
    return s

class Score:
    """
    The Score class is used to collect measurements from a server and derive a total score.
    """
    def __init__(self):
        # Maximum score
        self.score_max = 1000
        
        # For each polling time, we set the added score to 0 if the rtt is
        # "good enough" in an attempt to make the playing field level.
        # In seconds.
        self.rtt_good_enough = 0.4
        
        # Multiply the HTTP RTT by N before adding to score.
        # 50: rtt of 2.4 seconds will add 60 to score.
        self.http_rtt_mul = 50
        
        # Multiply the TCP APRS-IS rtt by N before adding to score.
        # It will be divided by the number of APRS-IS ports successfully polled (ipv4, ipv6: 2)
        self.aprsis_rtt_mul = 40
        
        # poll time, in seconds (float), per address family ("ipv4", "ipv6")
        self.poll_t_14580 = {}
        
        # http status poll time
        self.http_status_t = None
        
        self.score = 0
        self.score_components = {}
    
    def score_add(self, type, val, string):
        self.score += val
        self.score_components[type] = [ val, string ]
    
    def round_components(self):
        for i in self.score_components:
           if self.score_components[i][0] > 0.0:
               self.score_components[i][0] = int(self.score_components[i][0] * 10) / 10.0
        
    def get(self, props):
        """
        Calculate and return a total score. Best: 0, higher is worce.
        """
        
        #
        # HTTP
        #
        
        # We must have a working HTTP status.
        if self.http_status_t == None:
            return self.score_max
        
        self.score_add('http_rtt', max(0, self.http_status_t - self.rtt_good_enough) * self.http_rtt_mul,
        	'%.3f s' % self.http_status_t )
        
        #
        # APRS-IS
        #
        
        # We need at least one address family (ipv4, ipv6) working.
        if len(self.poll_t_14580) < 1:
            return self.score_max
        
        # Calculate an arithmetic average score based on 14580 RTT.
        is_score = 0
        rtt_sum = 0
        for k in self.poll_t_14580:
            t = self.poll_t_14580.get(k, 30) # default 30 seconds, if not found (should not happen)
            rtt_sum += t
            is_score += max(0.0, t - self.rtt_good_enough) * self.aprsis_rtt_mul
        
        is_score = is_score / len(self.poll_t_14580)
        rtt_avg = rtt_sum / len(self.poll_t_14580)
        self.score_add('aprsis_rtt', is_score,
        	'%.3f s' % rtt_avg)
        
        #
        # Amount of users
        #
        
        # Find the worst case load
        loads = [ props.get('worst_load', 100) ]
        
        load = max(loads)
        self.score_add('user_load', load*10.0, '%.1f %%' % load)
        
        self.round_components()
        
        #
        # Uptime
        #
        # If the server's uptime is low, it might be in a crashing loop or
        # unstable - low amount of users, but gets a very good score!
        # Give a bit of penalty for newly rebooted servers.
        uptime = props.get('uptime')
        if uptime != None:
            score_range = 30.0*60.0 # 30 minutes
            uptime_max_penalty = 500.0
            if uptime < 0:
                uptime = 0
            if uptime < score_range:
            	penalty = (score_range - uptime) / score_range * uptime_max_penalty
            	uptime_s = dur_str(uptime)
                self.score_add('uptime', penalty, uptime_s)
        
        return self.score

