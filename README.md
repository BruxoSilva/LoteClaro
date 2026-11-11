# Lote Claro — controle financeiro local

Sistema completo para lotes, clientes, vendas, despesas, estoque, fechamento e relatório PDF. Interface em português, sem dados demonstrativos no banco de uso. Os arquivos em `Exemplo PDF` foram preservados. O relatório reproduz a organização visual da imagem: título de fechamento, nota de conferência, seções numeradas, tabelas claras, totais e destaques verdes/vermelhos. As seções de pagamentos da referência foram adaptadas às informações efetivamente solicitadas (vendas, despesas e resultados).

## Repositório e privacidade

O repositório contém somente código-fonte, telas, testes e arquivos de configuração de exemplo. O banco SQLite real, backups, relatórios, perfil do aplicativo, referências locais e o executável compilado são ignorados pelo Git para impedir a publicação acidental de dados pessoais ou financeiros.

Após clonar, as pastas de dados já existem por meio de arquivos `.gitkeep`. Para configurar o aplicativo compilado, copie `Programa\lote-claro.example.json` para `Programa\lote-claro.json` e ajuste `data_directory`. Nunca publique o arquivo de configuração local, o banco `data\calculadora.db`, a pasta `backups` ou os relatórios gerados.

Para publicar pela primeira vez:

```powershell
git add .
git commit -m "Versão inicial do Lote Claro"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
git push -u origin main
```

## Aplicativo para Windows

O programa compilado está em `Programa\LoteClaro.exe`. Dê dois cliques nele para abrir o sistema em uma janela própria. O arquivo `Programa\lote-claro.json` aponta para esta pasta do projeto, por isso o aplicativo usa o banco existente em `data\calculadora.db` e preserva os relatórios e backups atuais.

Mantenha `LoteClaro.exe` e `lote-claro.json` juntos. O executável não contém o banco: registros, relatórios e backups continuam fora dele, permitindo substituir o programa em futuras atualizações sem substituir os dados. O aplicativo impede duas instâncias simultâneas e grava falhas técnicas em `logs\aplicativo.log`.

O histórico da calculadora e seu rascunho pertencem ao armazenamento do navegador onde foram criados. Na aba Calculadora, use **Transferir histórico e rascunho**: exporte no navegador antigo e importe no aplicativo. A importação acrescenta o conteúdo, evita duplicação em importações repetidas e guarda uma cópia do estado anterior no armazenamento do aplicativo.

Para recompilar depois de mudanças, execute `compilar_programa.bat`. A compilação requer internet apenas para instalar as ferramentas na primeira execução. O Microsoft Edge WebView2 Runtime, normalmente instalado com o Edge no Windows, é necessário para a janela própria.

O acesso remoto pelo telefone será integrado na etapa final. Até essa configuração, o executável funciona localmente e os scripts de navegador existentes continuam disponíveis separadamente.

## Iniciar neste computador

O ambiente Python e o banco vazio já foram preparados nesta pasta. Dê dois cliques em **iniciar.bat**. O navegador abrirá em **http://127.0.0.1:5000**. Mantenha a janela do programa aberta; para encerrar, pressione `Ctrl+C` nessa janela. Os dados permanecem salvos.

No PowerShell:

```powershell
Set-Location 'D:\Site calculadora'
.\iniciar.bat
```

Ou diretamente:

```powershell
.\.venv\Scripts\python.exe run.py
```

Não execute duas instâncias simultâneas. Se a porta 5000 estiver ocupada, encerre a outra instância ou use:

```powershell
.\.venv\Scripts\python.exe run.py --port 5001
```

`--no-browser` desativa a abertura automática do navegador. `--init-db` cria/verifica o esquema sem iniciar o servidor. Não há configuração externa obrigatória nem credenciais.

## Instalação em outro Windows

1. Instale Python 3.11 ou superior com a opção **Add Python to PATH**.
2. Copie o projeto para uma pasta com permissão de gravação. Não copie `.venv` de outro computador; o instalador recria esse ambiente.
3. Execute `instalar.bat`. Ele cria `.venv`, instala as dependências de `requirements.txt` e cria as tabelas automaticamente.
4. Execute `iniciar.bat`.

A instalação inicial de bibliotecas requer internet. **Depois da instalação, toda a operação é local e funciona sem internet**, incluindo geração de PDF. Não há CDN, fontes remotas, API, nuvem, Docker ou telemetria. O serviço escuta somente `127.0.0.1`. Use Chrome, Edge ou Firefox atualizado.

Para instalação sem internet, prepare previamente uma pasta de pacotes em um Windows com a mesma versão de Python e arquitetura:

```powershell
python -m pip download -r requirements.txt -d pacotes
```

Copie `pacotes` para a máquina de destino, crie o ambiente e instale:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links pacotes -r requirements.txt
.\.venv\Scripts\python.exe run.py --init-db
```

## Uso

1. **Lotes → Cadastrar lote:** informe granja, retirada, cabeças, entrada, peso pago e custo por kg. Os dois pesos são obrigatórios e independentes.
2. **Clientes:** exige somente nome. Em **Vendas**, também é possível preencher “Cadastrar novo cliente agora”; isso cria o cliente e a venda na mesma transação. Se escolher um cliente e digitar um novo nome, prevalece o novo nome, como indicado no formulário.
3. **Vendas / Despesas:** selecione um lote aberto. Lance os registros. O total da venda aparece automaticamente; o servidor recalcula e valida os valores ao salvar.
4. No detalhamento, use **Editar** ou **Excluir**. Alterações exigem confirmação; exclusões abrem uma página específica com confirmação. Os totais são calculados a partir dos registros atuais, evitando totais desatualizados.
5. **Estoque:** consulte entrada, peso vendido, saldo, quebra ou excedente. O painel também permite buscar código ou granja.
6. **Conferir e finalizar:** confira todos os dados, vendas, despesas e cálculos. Havendo saldo, responda se ele ainda existe fisicamente. A resposta “Sim” impede o encerramento; “Não” reconhece o saldo como quebra. Confirme o bloqueio para finalizar.
7. O PDF é gerado automaticamente e salvo. **Baixar PDF** obtém o arquivo. **Gerar novamente** cria uma nova cópia. Lotes abertos também permitem PDF parcial, identificado como aberto.
8. **Histórico:** consulte lotes finalizados. **Reabrir lote** exige confirmação, libera edição e reclassifica a quebra como estoque. PDFs antigos permanecem na pasta; novas alterações não modificam documentos históricos.

Não há exclusão de lotes ou clientes na interface, preservando o histórico. Somente lançamentos podem ser excluídos, após confirmação. O nome do cliente é registrado também na venda para preservar o documento histórico.

## Regras, precisão e limites

- Pesos: até **3 casas decimais**, armazenados como gramas inteiras.
- Preço por kg e despesas: até **2 casas decimais**, armazenados como centavos inteiros.
- Digite `1234,56` ou `1234.56`, **sem separador de milhares**. A exibição usa `R$ 1.234,56`, kg e `DD/MM/AAAA`.
- Cabeças: inteiro positivo. Entrada, peso pago e peso vendido: maiores que zero. Preços podem ser zero; despesas devem ser positivas. Datas devem existir; lançamentos não podem ser anteriores à retirada. A retirada não pode ser editada para depois de lançamentos existentes.
- Cada valor numérico escalado tem limite de 10¹²; cabeças até 10⁹. Campos de nome têm até 160 caracteres; descrição de despesa, 300; observação, 500. Nomes/observações são uma linha.
- Todas as multiplicações financeiras usam `Decimal`, com arredondamento comercial (`ROUND_HALF_UP`) para centavos. A receita soma os **totais arredondados de cada venda**. A prévia no navegador usa `BigInt`, sem ponto flutuante financeiro.
- Custo da entrada = entrada × custo por kg. Custo principal = **(peso pago original − PERCAS) × custo por kg**. Ambos são apresentados.
- Receita = soma das vendas. Lucro bruto = receita − custo do peso pago líquido.
- Lucro líquido = receita − custo do peso pago líquido − despesas − quebra. Esta regra desconta a quebra adicionalmente ao custo integral, exatamente conforme solicitado; não é um cálculo proporcional de custo apenas das mercadorias vendidas.
- Margem = lucro líquido / receita × 100; receita zero produz margem de 0%.
- Em aberto, saldo positivo é estoque; no fechamento confirmado sem estoque físico, torna-se quebra. O estoque final disponível passa a zero e o peso da quebra fica destacado.
- Excedente = peso vendido − entrada quando positivo. Seu valor usa o custo por kg e é apenas indicador: **não é somado novamente ao lucro**.
- Venda acima da entrada é permitida para atender à regra de excedente. Diferença zero indica estoque conciliado.
- Resultados abertos são parciais e já consideram todo o custo do peso pago. Ao reabrir, deixam de reconhecer quebra até novo fechamento.

## Dados e estrutura

```text
D:\Site calculadora\
  app\                 servidor, regras financeiras, SQLite e PDF
    domain.py           cálculos e formatação exata
    db.py               esquema, criação automática, vínculos e bloqueios
    report.py           geração PDF com tabelas paginadas
    web.py              rotas, validação, fechamento, backup/restauração
  templates\           telas HTML em português
  static\              CSS e JavaScript locais
  tests\               testes automatizados isolados
  data\calculadora.db  banco SQLite de uso
  Relatorios\          PDFs gerados
  backups\             cópias de segurança
  Exemplo PDF\         referência original, não alterada
  run.py               entrada do servidor local
  instalar.bat         instalação
  iniciar.bat          inicialização e abertura do navegador
  testar.bat           instalação das ferramentas e execução de testes
  requirements.txt     dependências do sistema
  requirements-dev.txt dependências de testes e inspeção PDF
  README.md
```

SQLite usa tabelas relacionadas `lotes`, `clientes`, `vendas`, `despesas` e `percas`, chaves estrangeiras habilitadas, índices e versão de esquema `PRAGMA user_version=2`. Operações críticas usam transações. Um bloqueio de processo serializa as operações e protege a restauração. O fechamento verifica a revisão do lote para rejeitar resumos desatualizados. Falha na geração do PDF impede a confirmação do fechamento no banco. Edição comum de lote fechado é bloqueada pelo servidor; gatilhos adicionais impedem alteração de vendas/despesas finalizadas.

Os PDFs são escritos primeiro em arquivo temporário e renomeados ao concluir. Nomes incluem código, granja normalizada, data e sufixo único; documentos anteriores não são sobrescritos. Tabelas repetem cabeçalhos ao trocar de página e mantêm as linhas inteiras. Uma falha raríssima entre a gravação do PDF e a confirmação SQLite pode deixar um PDF extra sem fechamento correspondente; consulte sempre o estado do lote na interface.

## Backup

Na tela **Backup e restauração**, clique em **Criar e baixar backup**. A API de backup do SQLite cria uma cópia consistente mesmo com o sistema aberto. Ela é salva em `backups` e oferecida para download. Copie regularmente esse arquivo para outro disco ou pendrive.

O backup do banco contém todos os registros, mas **não inclui os PDFs**. Para preservar os documentos emitidos, copie também `Relatorios`. Com o sistema fechado, uma cópia completa da pasta do projeto também serve como backup (o ambiente `.venv` pode ser recriado).

Para copiar manualmente somente o banco, primeiro encerre o sistema com `Ctrl+C` e então copie `data\calculadora.db`. Evite copiar diretamente um banco em uso; prefira a tela de backup.

## Restauração

1. Entre em **Backup e restauração** e selecione um `.db` criado por esta versão (até 100 MB).
2. Leia o aviso e confirme explicitamente a substituição.
3. O programa verifica a integridade SQLite, vínculos e compatibilidade do esquema. Antes de substituir, grava automaticamente `backups\Antes_da_restauracao_*.db`.
4. Após restaurar, atualize as outras abas do sistema; formulários antigos são invalidados.
5. Os PDFs atuais não são removidos. Se faltarem arquivos do backup, restaure a pasta `Relatorios` que você guardou ou use **Gerar novamente** em cada lote.

Para desfazer uma restauração, restaure o arquivo `Antes_da_restauracao` correspondente.

Restauração manual com o serviço encerrado: renomeie o banco atual para guardá-lo, copie o backup para `data\calculadora.db` e inicie novamente. Não substitua arquivos enquanto o sistema estiver aberto. Guarde backups antes de atualizar versões futuras; versões com mudanças de esquema precisarão de migração correspondente.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Ou execute `testar.bat`. Os testes criam bancos e PDFs temporários, **não populam nem alteram o banco real**. Cobrem cálculos, arredondamento, saldo, quebra, excedente sem dupla contagem, receita zero, CRUD e recálculo, persistência, validação, proteção de requisições, fechamento/reabertura, backup/restauração, vínculos SQLite, falha de PDF e paginação extensa.

Validação de entrega em 03/11/2026: **23 testes aprovados**. Fluxo completo também verificado em Microsoft Edge automatizado, com tela de 1440 px e celular de 390 px, sem erros JavaScript ou transbordamento horizontal da página. PDF de fechamento de duas páginas e amostras de relatório extenso de dez páginas renderizados e inspecionados. Banco principal verificado vazio e com `PRAGMA integrity_check = ok`.

## Segurança e manutenção

Uso pessoal em uma máquina confiável: sem login ou criptografia de banco. Qualquer pessoa com acesso ao usuário Windows/pasta pode ler os dados. O servidor fica restrito ao computador local, valida o host e aplica tokens contra requisições externas, consultas parametrizadas e escape HTML. Não exponha a porta na rede ou na internet.

Se aparecer um erro, a interface apresenta a falha e a operação é revertida; detalhes técnicos de erros inesperados ficam no terminal do servidor. Confira permissões da pasta, espaço em disco e se a porta está livre. PDFs abertos em programas externos podem impedir operações manuais de cópia; feche o leitor antes de movê-los. Data/hora de geração segue o relógio/fuso configurado no Windows; configure-o para Brasília para registros locais corretos.

Não há conciliação bancária, recebimentos parcelados, emissão fiscal ou controle de usuários, pois não fazem parte do escopo. A soma das vendas é receita bruta independentemente do recebimento. A imagem foi usada como referência visual, e não como fonte de dados para preencher o sistema.


## PERCAS — desconto no peso pago

Disponível no cadastro de **Novo lote**, no lançamento de **nova venda**, no menu **PERCAS** e na seção **04 / PERCAS** do lote. Informe kg (até três casas decimais) e observação obrigatória explicando o que foi perdido. Na entrada usa a data da retirada; durante a venda usa a data da venda; no lançamento separado você informa a data.

O peso pago original fica preservado. O sistema soma as percas e calcula:

- Peso pago líquido = peso pago original − total de PERCAS.
- Custo principal = peso pago líquido × custo por kg.
- Lucro bruto, lucro líquido e margem são recalculados usando esse custo.

Exemplo: 95 kg pagos e 5 kg de PERCAS resultam em 90 kg líquidos. Com custo de R$ 5,20/kg, o custo principal passa de R$ 494,00 para R$ 468,00. O abatimento financeiro mostrado é a diferença entre os custos arredondados antes/depois, evitando divergências de centavos.

A entrada, as vendas, a receita e o custo da entrada mantêm suas bases originais. A regra de estoque/quebra continua comparando entrada e peso vendido. PERCAS é o abatimento no peso pago solicitado; não é lançado novamente como despesa. Se a perda também aparecer como diferença física no fechamento, a regra de quebra anteriormente definida continua sendo aplicada.

Cada PERCA é um lançamento independente do lote. Quando criada junto com uma venda, ambas são salvas na mesma transação; editar ou excluir a venda depois não altera a PERCA. Para corrigir a perda, use **Editar** ou **Excluir** na seção PERCAS, com confirmação. Não lance novamente a mesma perda ao editar uma venda. Lotes finalizados bloqueiam alterações de PERCAS até reabertura.

O total de PERCAS não pode exceder o peso pago original. É permitido que seja igual, deixando peso pago líquido e custo principal em zero. Também é bloqueada a redução do peso pago original para um valor menor que as percas já cadastradas. Alterações invalidam o link do PDF anterior para que o próximo download use um relatório atualizado; arquivos antigos permanecem preservados.

Na primeira abertura desta versão, a migração cria a tabela `percas` sem modificar registros existentes e salva uma cópia prévia em `backups/Antes_migracao_percas_*.db`. Backups da versão 1 continuam aceitos: são validados e migrados antes de restaurar. Reinicie o programa após atualizar o código.

Validação da atualização: **36 testes aprovados**, incluindo desconto financeiro, precisão, CRUD, bloqueio de finalizados, PDF, limite acumulado, transação conjunta e compatibilidade de backups antigos.


## Calculadora independente e calendários

A aba **Calculadora** é um rascunho separado de todos os lotes. Adicione quantos recebimentos precisar, informando valor recebido, nome do cliente, data da venda pelo calendário e forma de recebimento (Cheque ou Dinheiro). É possível editar e excluir itens, com confirmação para exclusões, além de escrever anotações gerais.

Clique em **Gerar relatório de cálculo na tela** para ver os recebimentos, total em cheques, total em dinheiro, total geral, totais por cliente e anotações. Os nomes são agrupados conforme digitados, desconsiderando apenas espaços no início/fim. Os cálculos usam centavos inteiros (`BigInt`); valores precisam ser positivos e ter até duas casas decimais. Alterações ocultam o resumo anterior até que seja gerado novamente.

**Nenhum lançamento da Calculadora é gravado no SQLite ou incluído nos cálculos, PDFs ou backups dos lotes. Nenhum arquivo é gerado por essa aba.** O rascunho é mantido somente no `sessionStorage` da aba do navegador, permitindo navegar no sistema e voltar, ou atualizar a página durante a mesma sessão. Não é um arquivo permanente: use **Limpar rascunho** para apagar recebimentos e anotações, e não dependa da recuperação após fechar a aba/navegador. Se o navegador bloquear esse armazenamento, o sistema avisa que o rascunho ficará apenas na memória da página.

Todos os campos de data editáveis (retirada, vendas, despesas, PERCAS e Calculadora) agora usam o calendário nativo do navegador (`date picker`). O valor interno enviado é ISO `AAAA-MM-DD`, sem conversão de fuso horário; relatórios e tabelas continuam em `DD/MM/AAAA`. A aparência do calendário segue o navegador e o idioma do Windows. Datas de criação/finalização continuam automáticas.

Validação desta atualização: **46 testes automatizados aprovados**, mais teste no Microsoft Edge para totais exatos, edição, confirmação de exclusão, recuperação na sessão, limpeza, proteção de texto, layout de celular e calendário. O teste do rascunho confirmou que nenhuma requisição de escrita foi enviada ao servidor.

Para repetir a verificação opcional de navegador, execute `tests/browser_server.py` com o Python do ambiente e, em outro terminal com o pacote Node `playwright` disponível, execute `node tests/calculator.browser.cjs`. O servidor de teste usa porta 5003 e banco temporário, nunca o banco principal. O teste usa Microsoft Edge instalado e salva apenas capturas de verificação na pasta temporária do Windows.
