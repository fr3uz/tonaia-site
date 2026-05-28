const path = require('path');
const http = require('http');

// Resolve module from the whatsapp directory
const qrcode = require(path.join(__dirname, 'node_modules', 'qrcode-terminal'));

http.get('http://localhost:3001/api/qr', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const json = JSON.parse(data);
    if (json.qr) {
      qrcode.generate(json.qr, { small: true });
      console.log('\n[WhatsApp] Escaneie o QR Code acima com seu WhatsApp.');
      console.log('[WhatsApp] Status:', json.status);
    } else {
      console.log('[WhatsApp] QR ainda nao gerado. Status:', json.status);
    }
  });
}).on('error', () => {
  console.log('[WhatsApp] Servico offline em localhost:3001');
});
