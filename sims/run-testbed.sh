#!/bin/bash
# exp.sh: launch experiment on IoT-lab, log & retrieve results from server

# Inspiration: https://gitlab.irisa.fr/0000H82G/traces/-/tree/master/scripts

#set -e

#---------------------- TEST ARGUMENTS ----------------------#
if [ "$#" -ne 6 ]; then
  echo "Usage: $0 <exp name> <firmware path> <logs dir> <exp duration (m)> <site> <list of nodes>"
  exit
fi
#---------------------- TEST ARGUMENTS ----------------------#

#--------------------- DEFINE VARIABLES ---------------------#
LOGIN="urke" # TODO test SSH at beginning
EXPNAME=$1
FIRMWARE=$2
LOGDIR=$3
DURATION=$4
SITE=$5
NODES=$6

IOTLAB="$LOGIN@$SITE.iot-lab.info"
NGDIR="${HOME}/vizaworkspace/contiki-ng-arurke"

# Retry given command with sleeps in between, exit if all failed
# From https://unix.stackexchange.com/questions/82598/how-do-i-write-a-retry-logic-in-script-to-keep-retrying-to-run-it-upto-5-times
function retry_cmd {
  local n=1
  local max=20
  local delay=30
  while true; do
    "$@" && break || {
      if [[ $n -lt $max ]]; then
        ((n++))
        echo "Command failed. Attempt $n/$max:"
        sleep $delay;
      else
        echo "The command has failed after $n attempts."
        exit 1
      fi
    }
  done
}

#----------------------- CATCH SIGINT -----------------------#
# For a clean exit from the experiment
trap ctrl_c INT
function ctrl_c() {
	echo "Terminating experiment."
	iotlab-experiment stop -i "$EXPID"
	exit 1
}

#-------------------- CONFIGURE FIRMWARE --------------------#
#sed -i "s/#define\ SEND_INTERVAL_SECONDS\ .*/#define\ SEND_INTERVAL_SECONDS\ $2/g" $CODEDIR/broadcast-example.c
#sed -i "s/#define\ SEND_BUFFER_SIZE\ .*/#define\ SEND_BUFFER_SIZE\ $3/g" $CODEDIR/broadcast-example.c
#sed -i "s/#define\ NB_PACKETS\ .*/#define\ NB_PACKETS\ $5/g" $CODEDIR/broadcast-example.c

#-------------------- LAUNCH EXPERIMENTS --------------------#
echo "Submitting experiment $EXPNAME"

# We had problems with intermittent failures on the iotlab-*** scripts,
# we therefore use a retry function to increase robustness

# Launch the experiment and obtain its ID.  Retry if it fails.
launch_cmd="iotlab-experiment submit -n $EXPNAME -d $DURATION -l $NODES --site-association $SITE,script=serial_script.sh"
SUBMIT_INFO=$(retry_cmd $launch_cmd) || exit 1
EXPID=$(echo "$SUBMIT_INFO" | grep id | cut -d' ' -f6) || exit 1

# Wait for the experiment to begin. Retry if it fails.
wait_start_cmd="iotlab-experiment wait -i $EXPID"
retry_cmd $wait_start_cmd

# Flash nodes. Retry if it fails.
flash_cmd="chronic iotlab-node --flash $FIRMWARE -i $EXPID"
retry_cmd $flash_cmd

# Wait for experiment termination. Retry if it fails.
wait_end_cmd="iotlab-experiment wait -i $EXPID --state Terminated"
retry_cmd $wait_end_cmd

#----------------------- RETRIEVE LOG -----------------------#
mkdir $LOGDIR

ssh $IOTLAB "cd ~/.iot-lab/${EXPID}/ && tar -czf $EXPNAME.tar.gz serial_output && rm serial_output"
scp "$IOTLAB":~/.iot-lab/${EXPID}/$EXPNAME.tar.gz $LOGDIR/$EXPNAME.tar.gz
cd $LOGDIR
tar -xf $EXPNAME.tar.gz && rm $EXPNAME.tar.gz

mv serial_output $EXPNAME.scriptlog
echo "Downloaded log: $EXPNAME.scriptlog"

exit 0
