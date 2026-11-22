# A monitored Linux server: the NRPE agent, the stock plugins, our custom Bash checks, and its role's service.
FROM ubuntu:24.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nagios-nrpe-server monitoring-plugins-basic nginx openssl sudo procps \
 && rm -rf /var/lib/apt/lists/* \
 && sed -i 's/^allowed_hosts=.*/allowed_hosts=127.0.0.1,10.43.0.10/' /etc/nagios/nrpe.cfg \
 && echo 'nagios ALL=(root) NOPASSWD: /usr/sbin/nginx' > /etc/sudoers.d/nagios-nginx && chmod 440 /etc/sudoers.d/nagios-nginx \
 && mkdir -p /run/nagios /backups /etc/ssl/files && chown nagios:nagios /run/nagios
COPY nrpe/estate.cfg /etc/nagios/nrpe.d/estate.cfg
COPY plugins/ /usr/local/lib/nagios/
COPY bin/ /usr/local/bin/
RUN chmod 755 /usr/local/lib/nagios/* /usr/local/bin/*
EXPOSE 5666
CMD ["/usr/local/bin/entrypoint"]
