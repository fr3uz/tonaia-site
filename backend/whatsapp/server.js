const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

const PORT = process.env.WHATSAPP_PORT || 3001;
const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: { headless: true, args: ['--no-sandbox'] }
});

let status = 'iniciando';
let ultimo_qr = '';

client.on('qr', qr => {
  ultimo_qr = qr;
  qrcode.generate(qr, { small: true });
  status = 'aguardando_qr';
  console.log('\n[WhatsApp] Escaneie o QR Code acima para conectar.\n');
});

client.on('ready', () => {
  status = 'conectado';
  console.log('[WhatsApp] Conectado com sucesso!');
});

client.on('disconnected', () => {
  status = 'desconectado';
  console.log('[WhatsApp] Desconectado.');
});

client.initialize();

app.get('/api/status', (_, res) => {
  res.json({
    status,
    numero: client.info?.wid?.user || null,
    nome: client.info?.pushname || null,
  });
});

app.get('/api/qr', (_, res) => {
  res.json({ qr: ultimo_qr, status });
});

app.post('/api/enviar', async (req, res) => {
  const { telefone, mensagem } = req.body;
  if (!telefone || !mensagem) {
    return res.status(400).json({ erro: 'telefone e mensagem sao obrigatorios' });
  }
  if (status !== 'conectado') {
    return res.status(503).json({ erro: 'WhatsApp nao conectado', status });
  }
  try {
    const chatId = telefone.includes('@c.us') ? telefone : `${telefone}@c.us`;
    await client.sendMessage(chatId, mensagem);
    res.json({ ok: true, para: telefone });
  } catch (e) {
    res.status(500).json({ erro: e.message });
  }
});

app.listen(PORT, () => {
  console.log(`[WhatsApp API] Rodando em http://localhost:${PORT}`);
});
