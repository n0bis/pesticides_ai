FROM bde2020/spark-python-template:3.1.1-hadoop3.2

RUN apk add --no-cache py3-numpy

RUN apk --no-cache add --virtual build-deps musl-dev linux-headers g++ gcc python3-dev

# Copy the requirements.txt first, for separate dependency resolving and downloading
COPY app_requirements.txt /app/
RUN cd /app \
      && pip3 install -r app_requirements.txt


COPY submit.sh /

ENV ENABLE_INIT_DAEMON false
ENV SPARK_SUBMIT_ARGS "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2"

CMD ["/bin/bash", "/template.sh"]