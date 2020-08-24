# VERSION 0.0.2
FROM ubuntu:latest
MAINTAINER Gert Kanter <gert.kanter@ttu.ee>
LABEL Description="Hodor prolog container"

ENV TZ=Europe/Tallinn
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update
RUN apt-get install -y python3 rsyslog && rsyslogd
ENV TERM=xterm

RUN apt-get install -y swi-prolog

RUN mkdir /pkg

# install testing library (passing 2 into stdin of swipl should select /usr/lib/swi-prolog/pack as the folder)
ADD eplunit-1.0.0.zip /pkg
RUN cd /pkg && echo 2 | swipl -g "pack_install('eplunit-1.0.0.zip')" -t halt

# Add the tester
# Comment this line out when developing locally
ADD new_tester.py /pkg

# timeout is handled by Arete
CMD /bin/bash -c "cd /pkg && timeout 5000 python3 new_tester.py < /host/input.json > /host/output.json"
