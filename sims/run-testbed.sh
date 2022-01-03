#!/bin/bash
# exp.sh: launch experiment on IoT-lab, log & retrieve results from server

# Inspiration: https://gitlab.irisa.fr/0000H82G/traces/-/tree/master/scripts

set -e

#---------------------- TEST ARGUMENTS ----------------------#
if [ "$#" -ne 5 ]; then
  echo "Usage: $0 <exp name> <firmware path> <logs dir> <exp duration (m)> <list of nodes>"
  exit
fi
#---------------------- TEST ARGUMENTS ----------------------#

#--------------------- DEFINE VARIABLES ---------------------#
LOGIN="urke" # TODO test SSH at beginning
EXPNAME=$1
FIRMWARE=$2
LOGDIR=$3
DURATION=$4
NODES=$5
SITE="grenoble"
IOTLAB="$LOGIN@$SITE.iot-lab.info"
NGDIR="${HOME}/vizaworkspace/contiki-ng-arurke"

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

#cd $EXPDIR/scripts
# Launch the experiment and obtain its ID
EXPID=$(iotlab-experiment submit -n $EXPNAME -d $DURATION -l $NODES --site-association $SITE,script=serial_script.sh | grep id | cut -d' ' -f6)

# Wait for the experiment to began
iotlab-experiment wait -i $EXPID

# Flash nodes
echo "Flashing nodes with $FIRMWARE"
chronic iotlab-node --flash $FIRMWARE -i $EXPID

# Wait for experiment termination
iotlab-experiment wait -i $EXPID --state Terminated

#----------------------- RETRIEVE LOG -----------------------#
mkdir $LOGDIR

ssh $IOTLAB "cd ~/.iot-lab/${EXPID}/ && tar -czf $EXPNAME.tar.gz serial_output && rm serial_output"
scp "$IOTLAB":~/.iot-lab/${EXPID}/$EXPNAME.tar.gz $LOGDIR/$EXPNAME.tar.gz
cd $LOGDIR
tar -xf $EXPNAME.tar.gz && rm $EXPNAME.tar.gz

mv serial_output $EXPNAME.scriptlog
echo "Downloaded log: $EXPNAME.scriptlog"

exit 0
