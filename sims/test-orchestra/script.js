var num_transmissions = 0;
var num_receptions = 0;
var nodes_done = 0;
var num_source_nodes = 2;

// Don't let the test run forever
TIMEOUT(48000000, log.testFailed());

while(true) {
  YIELD();
  
  logWithIdAndTS(msg);

  if(msg.contains("ERR : App")) {
    log.testFailed();
  }
  else if(msg.contains("Done")) {
    nodes_done++;
  }
  else if(msg.contains("Sim finished")) {
    log.testOK();
  }
  
  // End the sim 30 sec after all nodes report done
  if(nodes_done >= num_source_nodes) {
    GENERATE_MSG(30000, "Sim finished")
  }
}

function logWithIdAndTS(string) {
  log.log(Math.floor(time / 1000) + "\tID:" + id + "\t" + string + "\n");
}
