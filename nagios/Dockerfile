# The Nagios Core server: the scheduler, check_nrpe, the stock plugins, and our alert and self-heal scripts.
FROM ubuntu:24.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nagios4-core nagios-nrpe-plugin monitoring-plugins-basic monitoring-plugins-standard python3 \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /var/lib/nagios4/rw /var/lib/nagios4/spool/checkresults /var/log/nagios4 /run/nagios4 \
 && chown -R nagios:nagios /var/lib/nagios4 /var/log/nagios4 /run/nagios4
COPY nagios.cfg resource.cfg /etc/nagios4/
COPY objects/ /etc/nagios4/estate/
COPY bin/ /usr/local/bin/
RUN chmod 755 /usr/local/bin/*
CMD ["/usr/sbin/nagios4", "/etc/nagios4/nagios.cfg"]
