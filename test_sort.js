async function run() {
    const res = await fetch("http://127.0.0.1:8014/api/plazas_status");
    const data = await res.json();
    const agents = data.plazas[0].agents;
    agents.forEach(a => console.log(a.name, a.last_active));
    console.log("--- sorting ---");
    agents.sort((a,b) => (b.last_active||0) - (a.last_active||0));
    agents.forEach(a => console.log(a.name, a.last_active));
}
run();
