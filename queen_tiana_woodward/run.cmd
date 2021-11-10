docker build . -t queen_tiana_woodward:latest 
docker run --rm -e ENABLE_INIT_DAEMON=false --network confluent queen_tiana_woodward