docker build . -t henna_fetcher:latest 
docker run --rm --network confluent henna_fetcher