const fs = require('fs');
function stripVolatileAgentFields(agent) {
    if (!agent || typeof agent !== 'object') return agent;
    const cloned = { ...agent, card: { ...(agent.card || {}) } };
    delete cloned.last_active;
    delete cloned.login_history;
    return cloned;
}
async function getHash() {
    const res = await fetch("http://127.0.0.1:8014/api/plazas_status");
    const data = await res.json();
    const plaza = data.plazas[0];
    const isOnline = !!plaza.online;
    const card = plaza.card || {};
    const showInactive = true;
    const sortOrder = "active-new";
    const agents = plaza.agents || [];
    // sortAgents
    agents.sort((a,b) => b.last_active - a.last_active);
    const nextHash = JSON.stringify({
        key: plaza.url,
        online: !!isOnline,
        card,
        showInactive: !!showInactive,
        sortOrder,
        agents: agents.map(stripVolatileAgentFields)
    });
    return nextHash;
}
async function run() {
    const h1 = await getHash();
    console.log("Waiting 3s...");
    await new Promise(r => setTimeout(r, 3000));
    const h2 = await getHash();
    console.log("h1 === h2?", h1 === h2);
    if (h1 !== h2) {
        fs.writeFileSync("h1.json", h1);
        fs.writeFileSync("h2.json", h2);
    }
}
run();
