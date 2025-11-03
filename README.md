# Legendas Auto Translator

Sistema automatizado de traducao de legendas para arquivos MKV usando LibreTranslate. Processa bibliotecas de filmes e series, convertendo legendas em ingles para portugues brasileiro de forma completamente offline.

## 🎯 Caracteristicas

- **Traducao offline**: Usa LibreTranslate local, sem envio de dados para APIs externas
- **Processamento inteligente**: Pula arquivos ja processados ou com legendas em portugues
- **Otimizacao de recursos**: Reutiliza legendas .en.srt extraidas anteriormente
- **Processamento em lote**: Varre recursivamente diretorios de filmes e series
- **Preservacao de formatacao**: Mantem tags HTML e timing das legendas
- **Logs detalhados**: Registro completo de processamento e erros

## 📋 Pre-requisitos

- Docker e Docker Compose instalados
- Espaco em disco para modelos de traducao (~1GB)
- Arquivos MKV com legendas em ingles (formato SRT)

## 🚀 Instalacao

1. Clone o repositorio:
```bash
git clone https://github.com/cascodigital/legendas-auto-translator.git
cd legendas-auto-translator
```

2. Ajuste os caminhos no `docker-compose.yml`:
```yaml
volumes:
  - /seu/caminho/para/scripts:/app
  - /seu/caminho/para/movies:/movies
  - /seu/caminho/para/tv:/tv
  - /seu/caminho/para/temp:/temp
```

3. Execute manualmente com `docker compose up -d` ou agende com crontab (ver secao Agendamento)

## 📂 Estrutura de Pastas

O sistema utiliza 4 volumes principais:

| Volume | Caminho no Container | Funcao |
|--------|---------------------|---------|
| Scripts | `/app` | Codigo Python e arquivos de log |
| Filmes | `/movies` | Biblioteca de filmes MKV |
| Series | `/tv` | Biblioteca de series MKV |
| Temp | `/temp` | Registro de legendas SUP/PGS |

## ⚙️ Configuracao

### Variaveis de Ambiente

- `TZ`: Fuso horario (padrao: `America/Sao_Paulo`)
- `TRANSLATE_API_URL`: URL da API LibreTranslate (padrao: `http://libretranslate:5000/translate`)

### Ajustes do LibreTranslate

No `docker-compose.yml`, voce pode modificar:

```yaml
environment:
  - LT_LOAD_ONLY=en,pt  # Idiomas a carregar
  - LT_THREADS=4        # Threads para processamento
```

## ⏰ Agendamento com Crontab

Para economizar recursos, execute o container apenas quando necessario usando crontab do host.

### Configuracao Recomendada

Edite o crontab do usuario:
```bash
crontab -e
```

Adicione as linhas:
```bash
# Processa legendas diariamente as 03:00
0 3 * * * cd /caminho/para/legendas-auto-translator && /usr/bin/docker compose up -d

# Limpeza semanal aos domingos as 04:00
0 4 * * 0 cd /caminho/para/legendas-auto-translator && /usr/bin/docker compose down
```

**O que isso faz:**
- Todo dia as 03:00: Inicia containers e processa legendas novas
- Domingo as 04:00: Para containers e libera memoria/recursos
- Volume de modelos e preservado (nao precisa baixar novamente)

### Outras Opcoes de Agendamento

Apenas aos sabados as 02:00:
```bash
0 2 * * 6 cd /caminho/para/legendas-auto-translator && /usr/bin/docker compose up -d
0 3 * * 6 cd /caminho/para/legendas-auto-translator && /usr/bin/docker compose down
```

Com registro de logs:
```bash
0 3 * * * cd /caminho/para/legendas-auto-translator && /usr/bin/docker compose up -d >> /var/log/legendas-cron.log 2>&1
```

### Verificar crontab configurado

```bash
crontab -l
```

**Dica**: O script e otimizado para multiplas execucoes - arquivos ja processados sao pulados automaticamente.

## 📊 Como Funciona

### Fluxo de Processamento

1. **Busca**: Varre diretorios `/movies` e `/tv` em busca de arquivos `.mkv`
2. **Verificacao de traducao**: Checa se ja existe `.pt-BR.srt` no mesmo diretorio
3. **Verificacao de portugues embutido**: Analisa faixas MKV para detectar legendas em portugues
4. **Reutilizacao**: Verifica se ja existe `.en.srt` extraido anteriormente
5. **Extracao**: Extrai legenda em ingles apenas se necessario
6. **Traducao**: Envia linha por linha para LibreTranslate
7. **Salvamento**: Cria arquivo `.pt-BR.srt` no mesmo diretorio do MKV

### Logica de Otimizacao

O script evita trabalho desnecessario seguindo esta ordem de verificacao:

**Pula arquivo se:**
- Ja existe `.pt-BR.srt` traduzido anteriormente
- O MKV ja possui faixa de legenda em portugues embutida (por, pt, pt-BR)

**Reutiliza extracao se:**
- Ja existe `.en.srt` no diretorio (nao extrai novamente do MKV)

**Registra e pula se:**
- Apenas legendas SUP/PGS encontradas (formato grafico, nao traduzivel)

### Casos Especiais

- **Legendas SUP/PGS**: Registradas em `/temp/legendassup.txt` para revisao manual
- **Multiplas faixas**: Prioriza primeira faixa de texto em ingles encontrada
- **Erros de extracao**: Registrados em log sem interromper processamento de outros arquivos

## 📝 Logs

Os logs sao salvos em `/app/subtitle_translator.log` dentro do container.

Para visualizar em tempo real:
```bash
docker logs -f legendas
```

## 🔍 Exemplo de Uso

Estrutura de arquivos antes:
```
/movies/
  ├── Filme.2023.1080p.mkv (com legenda ingles embutida)
  └── Outro.Filme.2024.mkv
```

Estrutura apos processamento:
```
/movies/
  ├── Filme.2023.1080p.mkv
  ├── Filme.2023.1080p.en.srt      ← Extraido do MKV
  ├── Filme.2023.1080p.pt-BR.srt   ← Traduzido
  ├── Outro.Filme.2024.mkv
  ├── Outro.Filme.2024.en.srt
  └── Outro.Filme.2024.pt-BR.srt
```

Segunda execucao pula todos os arquivos (ja processados).

## 🛠️ Resolucao de Problemas

### Container LibreTranslate nao inicia
- Verifique se a porta 5000 esta disponivel
- Aumente memoria disponivel para Docker (minimo 2GB)

### Legendas nao sao extraidas
- Confirme que o arquivo MKV possui legendas SRT em ingles
- Verifique logs: `docker logs legendas`
- Teste extracao manual: `mkvmerge -J arquivo.mkv`

### Traducao falha
- Aguarde alguns minutos - primeira execucao baixa modelos
- Verifique conectividade entre containers: `docker network inspect legendas_network`

### Crontab nao executa
- Verifique paths absolutos no crontab
- Confirme permissoes de execucao: `ls -l docker-compose.yml`
- Teste comando manualmente antes de agendar

## 🤝 Contribuicoes

Contribuicoes sao bem-vindas! Sinta-se a vontade para:
- Reportar bugs
- Sugerir novas funcionalidades
- Enviar pull requests

## 📄 Licenca

Este projeto esta licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

## ⚠️ Avisos

- Use apenas com conteudo que voce possui legalmente
- O processamento pode ser lento dependendo do hardware
- Legendas SUP/PGS (formato grafico) nao sao suportadas para traducao
- Execucoes subsequentes sao rapidas - arquivos processados sao pulados automaticamente

## 🔗 Links Uteis

- [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)
- [MKVToolNix](https://mkvtoolnix.download/)
- [Docker Documentation](https://docs.docker.com/)
- [Crontab Guru](https://crontab.guru/) - Gerador de expressoes cron
