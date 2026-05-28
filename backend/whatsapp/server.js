const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');
const fs = require('fs');

const app = express();
app.use(express.json());

const PORT = process.env.WHATSAPP_PORT || 3001;
const DONO_NUMERO = '554196380298';
const MENSAGENS_PATH = __dirname + '/mensagens.json';
const CONVERSAS_PATH = __dirname + '/conversas.json';

const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: { headless: true, args: ['--no-sandbox'] }
});

let status = 'iniciando';
let ultimo_qr = '';
let mensagens = [];
let conversas = {};

function carregarJSON(caminho, padrao) {
  try { return JSON.parse(fs.readFileSync(caminho, 'utf8')); }
  catch (e) { return padrao; }
}

function salvarJSON(caminho, dados) {
  fs.writeFileSync(caminho, JSON.stringify(dados, null, 2), 'utf8');
}

mensagens = carregarJSON(MENSAGENS_PATH, []);
conversas = carregarJSON(CONVERSAS_PATH, {});

function salvarMsg(registro) {
  mensagens.push(registro);
  salvarJSON(MENSAGENS_PATH, mensagens);
}

function getEstado(numero) {
  if (!conversas[numero]) conversas[numero] = { etapa: 'inicio', ultima: '' };
  return conversas[numero];
}

function setEstado(numero, dados) {
  conversas[numero] = { ...conversas[numero], ...dados };
  salvarJSON(CONVERSAS_PATH, conversas);
}

function notificarDono(texto) {
  const chatId = `${DONO_NUMERO}@c.us`;
  client.sendMessage(chatId, texto).catch(() => {});
}

const MENU = `🏪 *TôNaIA* — Seu negócio visível pra IA!

Como posso ajudar? Escolha uma opção:

1️⃣ *O que é TôNaIA?*
2️⃣ *Auditoria grátis*
3️⃣ *Ver planos*
4️⃣ *Falar com o Victor*
5️⃣ *Menu* (ver isso de novo)`;

const TEXTO_SOBRE = `🤖 *O que é TôNaIA?*

A TôNaIA otimiza seu negócio pra ser encontrado por IAs como ChatGPT, Gemini e Perplexity.

🔍 *Fazemos:*
• Auditoria de visibilidade pra IA
• Instalação de schema markup (código invisível que as IAs leem)
• Otimização do Google Business Profile
• Monitoramento semanal

💰 A partir de *R$200/mês* (plano mensal) ou *R$150/mês* (plano anual).

Digite *MENU* pra voltar.`;

const TEXTO_PLANOS = `📋 *Planos TôNaIA*

🥇 *Auditoria Única* — *Grátis*
Diagnóstico completo + PDF

🥈 *Mensal* — *R$200/mês*
Auditoria semanal + ajustes + suporte WhatsApp

🥉 *Anual* — *R$150/mês* (💰 *25% OFF!*)
R$1.800/ano — Tudo do Mensal + prioridade

🏆 *Premium* — *R$500/mês*
Site criado do zero + tudo incluso

Digite *MENU* pra voltar.`;

const TEXTO_AUDITORIA = `🔍 *Auditoria Grátis!*

Faça agora mesmo e descubra sua nota de 0 a 10:

👉 *http://localhost:5000/#auditor*

Digite *MENU* pra voltar.`;

const TEXTO_HUMANO = `👋 Certo! Já acionei o Victor pra falar com você.

Enquanto isso, você pode ir fazendo a auditoria grátis:
👉 *http://localhost:5000/#auditor*

Ele responde em breve!`;

function botResponder(corpo, nome) {
  const t = corpo.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();

  if (t === '1' || t === '1️⃣' || t.includes('oque e') || t.includes('o que e') || t.includes('tonaia') || t === 'sobre') {
    return { resposta: TEXTO_SOBRE, querHumano: false };
  }
  if (t === '2' || t === '2️⃣' || t.includes('audit') || t.includes('gratis') || t === 'diagnostico') {
    return { resposta: TEXTO_AUDITORIA, querHumano: false };
  }
  if (t === '3' || t === '3️⃣' || t.includes('plano') || t.includes('preco') || t.includes('preço') || t.includes('valor') || t.includes('mensal') || t.includes('anual') || t.includes('pago') || t.includes('quanto')) {
    return { resposta: TEXTO_PLANOS, querHumano: false };
  }
  if (t === '4' || t === '4️⃣' || t.includes('victor') || t.includes('falar') || t.includes('humano') || t.includes('pessoa') || t.includes('atendente') || t.includes('suporte') || t === '5' || t === '5️⃣') {
    return { resposta: TEXTO_HUMANO, querHumano: true };
  }
  if (t === '' || t.includes('menu') || t.includes('opcao') || t.includes('opção') || t.includes('oi') || t.includes('ola') || t.includes('olá') || t.includes('bom dia') || t.includes('boa tarde') || t.includes('boa noite') || t.includes('hey') || t.includes('eai') || t.includes('e aí') || t.includes('comecar') || t.includes('começar') || t.includes('voltar') || t === '5' || t === 'menu') {
    return { resposta: MENU, querHumano: false };
  }

  return { resposta: `Desculpe, ${nome}. Não entendi 😕\n\nDigite *MENU* pra ver as opções.`, querHumano: false };
}

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

client.on('message', async msg => {
  const de = msg.from.replace('@c.us', '');
  const nome = msg._data?.notifyName || 'desconhecido';
  const ehDono = de === DONO_NUMERO;

  const registro = {
    de, nome, corpo: msg.body,
    data: new Date().toISOString(), ehDono,
    id: msg.id?.id || Date.now().toString(),
  };
  salvarMsg(registro);

  if (!ehDono) {
    console.log(`\n[MSG] ${nome} (${de}): "${msg.body}"`);
  }
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

app.get('/api/mensagens', (_, res) => {
  res.json(mensagens.slice(-50).reverse());
});

app.get('/api/mensagens/nao-lidas', (_, res) => {
  const naoLidas = mensagens.filter(m => !m.ehDono && !m.lida).slice(-20).reverse();
  res.json(naoLidas);
});

app.post('/api/mensagens/marcar-lida', (req, res) => {
  const { id } = req.body;
  const msg = mensagens.find(m => m.id === id);
  if (msg) { msg.lida = true; salvarJSON(MENSAGENS_PATH, mensagens); res.json({ ok: true }); }
  else res.status(404).json({ erro: 'mensagem nao encontrada' });
});

app.post('/api/testar-bot', (req, res) => {
  const { mensagem } = req.body;
  if (!mensagem) return res.status(400).json({ erro: 'mensagem obrigatoria' });

  const { resposta, querHumano } = botResponder(mensagem, 'Teste');
  res.json({
    sua_msg: mensagem,
    resposta_bot: resposta,
    chamou_humano: querHumano
  });
});

app.listen(PORT, () => {
  console.log(`[WhatsApp API] Rodando em http://localhost:${PORT}`);
});
