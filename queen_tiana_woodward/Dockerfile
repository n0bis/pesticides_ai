FROM bde2020/spark-submit:3.1.1-hadoop3.2

# Add build dependencies for c-libraries (important for building numpy and other sci-libs)
RUN apk --no-cache add --virtual build-deps musl-dev linux-headers g++ gcc python3-dev

# Copy the requirements.txt first, for separate dependency resolving and downloading
ONBUILD COPY requirements.txt /app/
ONBUILD RUN pip3 install -r /app/requirements.txt

ONBUILD COPY main.py /app/

ENV SPARK_APPLICATION_PYTHON_LOCATION /app/main.py
ENV SPARK_SUBMIT_ARGS "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2"