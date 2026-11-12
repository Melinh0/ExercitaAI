import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)

CONVERSAO_TIMEOUT = int(os.getenv('OFFICE_CONVERSION_TIMEOUT', '300'))

EXTENSOES_OFFICE = ('.pptx', '.ppt', '.docx', '.doc')


def converter_para_pdf(caminho_origem):
    if not os.path.exists(caminho_origem):
        raise FileNotFoundError(caminho_origem)
    pasta_temp = tempfile.mkdtemp(prefix='office_conv_')
    try:
        processo = subprocess.run(
            [
                'soffice', '--headless', '--norestore', '--convert-to',
                'pdf', '--outdir', pasta_temp, caminho_origem,
            ],
            capture_output=True,
            timeout=CONVERSAO_TIMEOUT,
        )
        base = os.path.splitext(os.path.basename(caminho_origem))[0]
        pdf_gerado = os.path.join(pasta_temp, base + '.pdf')
        if processo.returncode != 0 or not os.path.exists(pdf_gerado):
            logger.error(
                f"Conversao de '{caminho_origem}' falhou "
                f"(rc={processo.returncode}): {processo.stderr.decode('utf-8', 'ignore')[:500]}"
            )
            raise RuntimeError('Falha ao converter o documento para PDF.')
        return pdf_gerado, pasta_temp
    except Exception:
        limpar(pasta_temp)
        raise


def limpar(pasta_temp):
    try:
        if pasta_temp and os.path.exists(pasta_temp):
            for nome in os.listdir(pasta_temp):
                try:
                    os.remove(os.path.join(pasta_temp, nome))
                except Exception:
                    pass
            os.rmdir(pasta_temp)
    except Exception:
        pass
