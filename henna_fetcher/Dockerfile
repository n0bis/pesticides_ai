FROM python:3.7

WORKDIR /usr/src/app

RUN apt-get update ##[edited]
RUN apt-get install ffmpeg libsm6 libxext6  -y

RUN pip install --upgrade pip

COPY requirements.txt ./
COPY test.png ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./timelapse.py" ]