#!/bin/bash

export SPARK_MASTER_URL=spark://${SPARK_MASTER_NAME}:${SPARK_MASTER_PORT}
export SPARK_HOME=/spark

function is_uri() {
    regex='(https?|hdfs|file)://[-A-Za-z0-9\+&@#/%?=~_|!:,.;]*[-A-Za-z0-9\+&@#/%=~_|]'
    if [[ $1 =~ $regex ]]
    then 
        echo "true"
    else
        echo "false"
    fi
}


/wait-for-step.sh


/execute-step.sh
if [[ `is_uri $SPARK_APPLICATION_PYTHON_LOCATION`=="true" || -f "${SPARK_APPLICATION_PYTHON_LOCATION}" ]]; then
    echo "Submit application ${SPARK_APPLICATION_PYTHON_LOCATION} to Spark master ${SPARK_MASTER_URL}"
    echo "Passing arguments ${SPARK_APPLICATION_ARGS}"
    PYSPARK_PYTHON=python3  /spark/bin/spark-submit \
        --master ${SPARK_MASTER_URL} \
        ${SPARK_SUBMIT_ARGS} \
        ${SPARK_APPLICATION_PYTHON_LOCATION} ${SPARK_APPLICATION_ARGS}
else
    echo "Not recognized application."
fi
/finish-step.sh