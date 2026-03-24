BaseAgent behavior:
* local pool is necessary
* register on plaza, get id and API key from plaza and store it to local pool
* once has id, never reregister on the same plaza
* heartbeat to plaza
* accept request from other agent, response data or error

StandbyAgent behavior:
* the BaseAgent should make sure only 1 credential is stored for a plaza. 
* if no credential for the plaza exist, register on the plaza and get a new one from the plaza. 
* if any credential exist, use the credential to register itself on the plaza. 
* if rejected by the plaza, don't ask new credential, wait for 1 minute and retry

when Plaza restart
* restore agent status and no need to reregister. 
* start api first and respond Starting to agents. 
* BaseAgent should keep retry hearbeats until the plaza back.