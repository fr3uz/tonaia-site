import os
import requests
import subprocess
import time
import threading

WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'http://localhost:3001')
NODE_PATH = os.path.join(os.path.dirname(__file__), 'whatsapp')

_processo = None


def iniciar():
    global _processo
    if _processo and _processo.poll() is None:
        return {'status': 'ja_rodando'}
    try:
        _processo = subprocess.Popen(
            ['node', 'server.js'],
            cwd=NODE_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        time.sleep(3)
        return {'status': 'iniciado', 'pid': _processo.pid}
    except Exception as e:
        return {'status': 'erro', 'erro': str(e)}


def parar():
    global _processo
    if _processo and _processo.poll() is None:
        _processo.terminate()
        _processo.wait(timeout=10)
        _processo = None
        return {'status': 'parado'}
    return {'status': 'nao_rodando'}


def status():
    try:
        r = requests.get(f'{WHATSAPP_API_URL}/api/status', timeout=5)
        return r.json()
    except requests.exceptions.ConnectionError:
        return {'status': 'offline'}


def qr_code():
    try:
        r = requests.get(f'{WHATSAPP_API_URL}/api/qr', timeout=5)
        return r.json()
    except requests.exceptions.ConnectionError:
        return {'status': 'offline'}


def enviar(telefone, mensagem):
    try:
        r = requests.post(
            f'{WHATSAPP_API_URL}/api/enviar',
            json={'telefone': telefone, 'mensagem': mensagem},
            timeout=15,
        )
        return r.json()
    except requests.exceptions.ConnectionError:
        return {'erro': 'WhatsApp service offline'}


def enviar_para_leads(nicho=None, cidade=None, mensagem_template=None):
    from prospector import listar_leads
    leads = listar_leads(categoria=nicho, cidade=cidade, com_telefone=True)
    if not mensagem_template:
        mensagem_template = (
            'Ola! Somos a TonaIA. Identificamos que seu negocio '
            'pode estar invisivel para IAs como ChatGPT e Gemini. '
            'Oferecemos auditoria gratuita. Quer saber mais?'
        )
    resultados = []
    for lead in leads:
        telefone = lead.get('telefone', '')
        if not telefone:
            continue
        tel_limpo = telefone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
        if not tel_limpo.startswith('55'):
            tel_limpo = '55' + tel_limpo
        res = enviar(tel_limpo, mensagem_template)
        resultados.append({'telefone': telefone, 'resultado': res})
        time.sleep(3)
    return {'enviados': len(resultados), 'resultados': resultados}
