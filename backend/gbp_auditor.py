class GBPAuditor:
    def __init__(self, nome, endereco=None, telefone=None, categoria=None):
        self.nome = nome
        self.endereco = endereco
        self.telefone = telefone
        self.categoria = categoria

    def audit(self):
        checks = {}
        total = 0

        if self.nome and len(self.nome) > 2:
            checks['nome'] = {'score': 1, 'max': 1, 'msg': 'Nome preenchido'}
        else:
            checks['nome'] = {'score': 0, 'max': 1, 'msg': 'Nome ausente ou inválido'}

        if self.endereco and len(self.endereco) > 10:
            checks['endereco'] = {'score': 1, 'max': 1, 'msg': 'Endereço preenchido'}
        else:
            checks['endereco'] = {'score': 0, 'max': 1, 'msg': 'Endereço ausente ou incompleto'}

        if self.telefone:
            digits = ''.join(filter(str.isdigit, self.telefone))
            if len(digits) >= 10:
                checks['telefone'] = {'score': 1, 'max': 1, 'msg': 'Telefone válido'}
            else:
                checks['telefone'] = {'score': 0.5, 'max': 1, 'msg': 'Telefone incompleto'}
        else:
            checks['telefone'] = {'score': 0, 'max': 1, 'msg': 'Telefone ausente'}

        if self.categoria:
            checks['categoria'] = {'score': 1, 'max': 1, 'msg': f'Categoria: {self.categoria}'}
        else:
            checks['categoria'] = {'score': 0, 'max': 1, 'msg': 'Categoria ausente'}

        total = sum(c['score'] for c in checks.values())
        max_total = sum(c['max'] for c in checks.values())
        nota = round((total / max_total) * 10, 1) if max_total > 0 else 0

        return {
            'nome': self.nome,
            'nota': nota,
            'checks': checks,
            'detalhes': self._gerar_detalhes(checks)
        }

    def _gerar_detalhes(self, checks):
        detalhes = []
        for key, check in checks.items():
            if check['score'] < check['max']:
                detalhes.append(check.get('msg', f'{key} incompleto'))
        if not detalhes:
            detalhes.append('GBP com informações básicas preenchidas')
        return detalhes
