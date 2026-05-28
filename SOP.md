# TôNaIA — SOP (Standard Operating Procedure)

## Como pedir as coisas

Use frases diretas. Exemplos:

> "adiciona cliente [nome] [tel]"
> "roda diagnostico do [cliente]"
> "abre a ferramenta"
> "mostra relatorio do [cliente]"
> "prospecta [nicho] em [cidade]"

---

## 1. GESTÃO DE CLIENTES

### Adicionar cliente
```
"adiciona cliente [nome] [telefone]"
```

### Listar clientes
```
"mostra clientes"
```

### Ver detalhes do cliente
```
"detalhe do [nome]"
```

### Remover cliente
```
"remove cliente [nome]"
```

---

## 2. QUESTIONÁRIO

### Enviar link pro cliente
```
"gera link do questionario pro [nome]"
```
Abre WhatsApp com o link `http://localhost:5000/questionario?cliente=[NOME]`

### Ver se cliente respondeu
```
"checa questionario do [nome]"
```

---

## 3. DIAGNÓSTICO

### Rodar diagnóstico
```
"diagnostico do [nome]"
```
Executa:
1. Verificação automática via Google Places API
2. Cruzamento dados autodeclarados vs verificados
3. Nota final + breakdown por categoria
4. Plano de ação

### Ver resultado
```
"mostra diagnostico do [nome]"
```

---

## 4. RELATÓRIO

### Gerar PDF completo
```
"relatorio do [nome]"
```
Gera PDF completo com nota, radar chart, breakdown, plano de ação, verificação automática.

### Gerar PDF grátis
Público, sem auth — via POST `/api/relatorio-gratis` (json: `{nome, cidade}`)
Retorna PDF superficial: score + stats mercado + CTA pra comprar diagnóstico R$ 97.

### Gerar PDF com modo
POST `/api/relatorio-pdf` com `{modo: "gratis"|"completo"}` (auth required)

---

## 5. PROSPECÇÃO

### Buscar leads
```
"prospecta [nicho] em [cidade]"
```
Ex: `"prospecta barbeiro em Curitiba"`

### Ver leads salvos
```
"mostra leads"
```

### Exportar leads
```
"exporta leads"
```

---

## 6. INFRA

### Abrir ferramenta
```
"abre a ferramenta"
```
Inicia servidor + abre navegador em http://localhost:5000

### Parar servidor
```
"para o servidor"
```

### Backup manual
```
"faz backup"
```

### Ver status
```
"status do sistema"
```
Mostra: servidor rodando?, total clientes, total auditorias, última prospecção.

---

## 7. MANUTENÇÃO / MELHORIAS

### Pedir melhoria
```
"preciso de [funcionalidade]"
```
Ex: `"preciso de um campo de observacoes no cliente"`

### Reportar bug
```
"bug: [descricao]"
```

---

## 8. FLUXO COMPLETO (NOVO CLIENTE)

```
1. "adiciona cliente [nome] [telefone]"
2. "gera link do questionario pro [nome]"  → envia pro cliente
3. (cliente preenche)
4. "checa questionario do [nome]"           → confirmar que respondeu
5. "diagnostico do [nome]"                   → roda verificação + nota
6. "relatorio do [nome]"                     → gera PDF
7. Entrega PDF + recomendações pro cliente
```

---

## 11. CONCORRENTES

### Adicionar concorrente
```
POST /api/concorrentes/adicionar  (json: {cliente_id, nome, cidade})
```

### Verificar concorrentes
```
POST /api/concorrentes/verificar/<cliente_id>
```
Roda quick-check em todos concorrentes, compara scores, gera alertas.

### Listar alertas
```
GET /api/alertas
GET /api/alertas?cliente_id=1&nao_lidas=1
```

### Executar monitoramento (todos clientes ativos)
```
POST /api/monitoramento/executar
```

---

## 12. E-COMMERCE

- Schema Product + Offer + AggregateRating detectados automaticamente
- Nova dimensão `ecommerce` no scoring (4% do peso total)
- Produtos com preço no schema = melhor ranking em rich snippets
- Multi-produto: escala com número de produtos detectados

---

## 13. WHITE-LABEL (AGÊNCIAS)

### Criar agência
```
POST /api/agencias  (json: {nome, logo_url, cor_primaria, whatsapp, email})
```

### Vincular cliente à agência
```
PUT /api/clientes/<cliente_id>/agencia  (json: {agencia_id})
```

### Listar clientes da agência
```
GET /api/agencias/<agencia_id>/clientes
```

---

## 14. AGENDAMENTOS

- Auditoria semanal automática: roda segundas 08:00
- Backup automático: todo dia 23:00
- Monitoramento: a cada 168h (7 dias) — configurável no .env
