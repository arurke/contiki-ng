#!/bin/bash
# Script from : https://www.iot-lab.info/docs/tools/run-script/

# Redirect all nodes serial output to a file
readonly OUTFILE="${HOME}/.iot-lab/${EXP_ID}/serial_output"

serial_aggregator -i ${EXP_ID} 2> /dev/null 1> ${OUTFILE}

