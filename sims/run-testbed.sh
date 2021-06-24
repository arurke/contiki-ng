#!/bin/bash
# exp.sh: launch experiment on IoT-lab, log & retrieve results from server

# Inspiration: https://gitlab.irisa.fr/0000H82G/traces/-/tree/master/scripts


set -e

#---------------------- TEST ARGUMENTS ----------------------#
if [ "$#" -ne 6 ]; then
	#echo "Usage: $0 <exp name> <interval (s)> <payload size (B)> <exp duration (m)> <packets per seconds> <list of nodes>"
	echo "Usage: $0 <exp name> <code path> <logs path> <exp duration (m)> <list of nodes> <flags to make>"
	exit
fi
#---------------------- TEST ARGUMENTS ----------------------#

#--------------------- DEFINE VARIABLES ---------------------#
LOGIN="urke"
EXPNAME=$1
DURATION=$4
NODES=$5
SITE="grenoble"
IOTLAB="$LOGIN@$SITE.iot-lab.info"
NGDIR="${HOME}/vizaworkspace/contiki-ng-arurke"
APPLICATION=node

#CODEDIR="${NGDIR}/sims/test-orchestra/code"
CODEDIR=$2

EXPDIR="${NGDIR}/sims/test-orchestra/testbed"

#LOGDIR="${NGDIR}/sims/executions/$EXPNAME/logs
LOGDIR=$3

TARGET=iotlab
FIRMWARE=${CODEDIR}/${APPLICATION}.${TARGET}
MAKEFLAGS_FROM_CLI=$6
CFLAGSEXTRA="-DTESTBED=1 ${MAKEFLAGS_FROM_CLI}"

#--------------------- DEFINE VARIABLES ---------------------#

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


#--------------------- COMPILE FIRMWARE ---------------------#
echo "Compiling firmware in $CODEDIR with extra flags: $CFLAGSEXTRA"
#cd $CODEDIR
#make TARGET=iotlab-m3 -j8 || { echo "Compilation failed."; exit 1; }
make -C $CODEDIR CFLAGSEXTRA="$CFLAGSEXTRA" ARCH_PATH=${NGDIR}/iot-lab-contiki-ng/arch/ CONTIKI=${NGDIR} TARGET=${TARGET} BOARD=m3 -j8 || { echo "Compilation failed."; exit 1; }


#-------------------- LAUNCH EXPERIMENTS --------------------#
echo "Submitting experiment $EXPNAME"

#cd $EXPDIR/scripts
# Launch the experiment and obtain its ID
EXPID=$(iotlab-experiment submit -n $EXPNAME -d $DURATION -l $NODES --site-association $SITE,script=serial_script.sh | grep id | cut -d' ' -f6)

# Wait for the experiment to began
iotlab-experiment wait -i $EXPID

# Flash nodes
echo "Flashing nodes with $FIRMWARE"
iotlab-node --flash $FIRMWARE -i $EXPID 

# Wait for experiment termination
iotlab-experiment wait -i $EXPID --state Terminated


#----------------------- RETRIEVE LOG -----------------------#
ssh $IOTLAB "tar -C ~/.iot-lab/${EXPID}/ -cvzf $EXPNAME.tar.gz serial_output"

# Ad-hoc while we don't have run concept 
#mkdir $LOGDIR/

scp "$IOTLAB":~/$EXPNAME.tar.gz $LOGDIR/$EXPNAME.tar.gz
cd $LOGDIR
tar -xvf $EXPNAME.tar.gz

mv serial_output $EXPNAME.scriptlog
echo "Downloaded log: $EXPNAME.scriptlog"

exit 0

