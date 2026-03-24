async function run() {
    try {
        const res = await fetch("http://127.0.0.1:8014/api/plazas_status");
        const data = await res.json();
        console.log(JSON.stringify(data.plazas[0].agents.map(a => ({ name: a.name, type: a.pit_type, act: a.last_active })), null, 2));
    } catch (e) {
        console.error(e);
    }
}
run();
