const coap = require('coap');
const server = coap.createServer();

// Variabile globale per memorizzare il dato
let storedData = "Nessun dato memorizzato.";

server.on('request', function(req, res) {
  const method = req.method;
  const url = req.url;

  console.log(`\n[RX] Ricevuto metodo: ${method} sul path: ${url}`);

  switch (method) {
    case 'GET':
      // Restituisce l'ultimo dato salvato
      console.log(`   --> Inviando al client: ${storedData}`);
      res.code = '2.05'; // Content
      res.end(storedData);
      break;

    case 'POST':
    case 'PUT':
      // Memorizza il payload ricevuto
      if (req.payload && req.payload.length > 0) {
        storedData = req.payload.toString();
        console.log(`   📦 Dato salvato (${method}): ${storedData}`);
        res.code = '2.04'; // Changed
        res.end(`Dato memorizzato con successo tramite ${method}`);
      } else {
        console.log(`   ⚠️ Tentativo di ${method} con payload vuoto.`);
        res.code = '4.00'; // Bad Request
        res.end('Errore: Payload vuoto');
      }
      break;

    case 'DELETE':
      // Resetta la variabile
      storedData = "Dato cancellato.";
      console.log('   🔴 Risorsa resettata su richiesta DELETE.');
      res.code = '2.02'; // Deleted
      res.end('Dato cancellato sul server CoAP');
      break;

    default:
      res.code = '4.05'; // Method Not Allowed
      res.end('Metodo non supportato');
      break;
  }
});

server.listen(function() {
  console.log('🚀 Server CoAP (Node.js) interattivo in ascolto sulla porta 5683...');
  console.log('Pronto per testare GET, POST, PUT e DELETE dall\'App IoTool.');
});