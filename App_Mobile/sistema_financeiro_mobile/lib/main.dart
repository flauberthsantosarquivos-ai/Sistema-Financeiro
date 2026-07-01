import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const SistemaFinanceiroApp());
}

const String apiBaseUrl = 'http://192.168.100.235:8001/api/mobile';

class SistemaFinanceiroApp extends StatelessWidget {
  const SistemaFinanceiroApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sistema Financeiro',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF2563EB),
        useMaterial3: true,
      ),
      home: const InicioMobilePage(),
    );
  }
}

class InicioMobilePage extends StatefulWidget {
  const InicioMobilePage({super.key});

  @override
  State<InicioMobilePage> createState() => _InicioMobilePageState();
}

class _InicioMobilePageState extends State<InicioMobilePage> {
  int indiceAtual = 0;

  @override
  Widget build(BuildContext context) {
    final paginas = [
      const PainelGerencialPage(),
      const AlimentacaoPage(),
      const PatrimonioPage(),
    ];
    final titulos = ['Sistema Financeiro', 'Alimentação', 'Patrimônio'];

    return Scaffold(
      backgroundColor: const Color(0xFFF1F5F9),
      appBar: AppBar(
        title: Text(titulos[indiceAtual]),
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
      ),
      body: paginas[indiceAtual],
      bottomNavigationBar: NavigationBar(
        selectedIndex: indiceAtual,
        onDestinationSelected: (indice) => setState(() => indiceAtual = indice),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Painel',
          ),
          NavigationDestination(
            icon: Icon(Icons.restaurant_outlined),
            selectedIcon: Icon(Icons.restaurant),
            label: 'Alimentação',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_outlined),
            selectedIcon: Icon(Icons.account_balance),
            label: 'Patrimônio',
          ),
        ],
      ),
    );
  }
}

class PainelGerencialPage extends StatefulWidget {
  const PainelGerencialPage({super.key});

  @override
  State<PainelGerencialPage> createState() => _PainelGerencialPageState();
}

class _PainelGerencialPageState extends State<PainelGerencialPage> {
  bool carregando = true;
  String? erro;
  Map<String, dynamic>? dados;

  @override
  void initState() {
    super.initState();
    carregarPainel();
  }

  Future<void> carregarPainel() async {
    setState(() { carregando = true; erro = null; });
    try {
      final resposta = await http.get(Uri.parse('$apiBaseUrl/painel-gerencial?ano=2026&mes=6'));
      if (resposta.statusCode != 200) throw Exception('Erro HTTP ${resposta.statusCode}');
      final jsonResposta = jsonDecode(resposta.body) as Map<String, dynamic>;
      if (jsonResposta['sucesso'] != true) throw Exception(jsonResposta['mensagem'] ?? 'Erro ao carregar dados');
      if (!mounted) return;
      setState(() { dados = Map<String, dynamic>.from(jsonResposta['dados'] as Map); carregando = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { erro = e.toString(); carregando = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final cards = (dados?['cards'] as List?) ?? [];
    final periodo = dados?['periodo']?['referencia'] ?? '---';
    if (carregando) return const Center(child: CircularProgressIndicator());
    if (erro != null) return _ErroPainel(erro: erro!, aoTentarNovamente: carregarPainel);
    return RefreshIndicator(
      onRefresh: carregarPainel,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Painel Gerencial', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text('Período: $periodo', style: const TextStyle(color: Color(0xFF64748B))),
          const SizedBox(height: 20),
          ...cards.map((card) => _CardFinanceiro(card: card)),
        ],
      ),
    );
  }
}

class AlimentacaoPage extends StatefulWidget {
  const AlimentacaoPage({super.key});

  @override
  State<AlimentacaoPage> createState() => _AlimentacaoPageState();
}

class _AlimentacaoPageState extends State<AlimentacaoPage> {
  bool carregando = true;
  String? erro;
  Map<String, dynamic>? dados;

  @override
  void initState() {
    super.initState();
    carregarAlimentacao();
  }

  Future<void> carregarAlimentacao() async {
    setState(() { carregando = true; erro = null; });
    try {
      final resposta = await http.get(Uri.parse('$apiBaseUrl/alimentacao'));
      if (resposta.statusCode != 200) throw Exception('Erro HTTP ${resposta.statusCode}');
      final jsonResposta = jsonDecode(resposta.body) as Map<String, dynamic>;
      if (jsonResposta['sucesso'] != true) throw Exception(jsonResposta['mensagem'] ?? 'Erro ao carregar alimentação');
      if (!mounted) return;
      setState(() { dados = Map<String, dynamic>.from(jsonResposta['dados'] as Map); carregando = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { erro = e.toString(); carregando = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (carregando) return const Center(child: CircularProgressIndicator());
    if (erro != null) return _ErroPainel(erro: erro!, aoTentarNovamente: carregarAlimentacao);

    final resumo = Map<String, dynamic>.from((dados?['resumo'] as Map?) ?? {});
    final contas = (dados?['contas'] as List?) ?? [];
    final movimentacoes = (dados?['movimentacoes'] as List?) ?? [];
    final referencia = dados?['periodo']?['referencia'] ?? '---';

    return RefreshIndicator(
      onRefresh: carregarAlimentacao,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Alimentação', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text('Saldos atuais · referência $referencia', style: const TextStyle(color: Color(0xFF64748B))),
          const SizedBox(height: 16),
          _DestaqueSaldo(valor: resumo['total_saldo_fmt']?.toString() ?? r'R$ 0,00'),
          const SizedBox(height: 16),
          Text('Contas', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          ...contas.map((conta) => _CardContaAlimentacao(conta: conta)),
          const SizedBox(height: 12),
          Text('Últimas movimentações', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          if (movimentacoes.isEmpty)
            const _Vazio(texto: 'Nenhuma movimentação encontrada neste mês.')
          else
            ...movimentacoes.map((mov) => _MovimentacaoAlimentacao(movimentacao: mov)),
        ],
      ),
    );
  }
}


class PatrimonioPage extends StatefulWidget {
  const PatrimonioPage({super.key});

  @override
  State<PatrimonioPage> createState() => _PatrimonioPageState();
}

class _PatrimonioPageState extends State<PatrimonioPage> {
  bool carregando = true;
  String? erro;
  Map<String, dynamic>? dados;

  @override
  void initState() {
    super.initState();
    carregarPatrimonio();
  }

  Future<void> carregarPatrimonio() async {
    setState(() {
      carregando = true;
      erro = null;
    });

    try {
      final resposta = await http.get(Uri.parse('$apiBaseUrl/patrimonio'));
      if (resposta.statusCode != 200) {
        throw Exception('Erro HTTP ${resposta.statusCode}');
      }

      final jsonResposta = jsonDecode(resposta.body) as Map<String, dynamic>;
      if (jsonResposta['sucesso'] != true) {
        throw Exception(jsonResposta['mensagem'] ?? 'Erro ao carregar patrimônio');
      }

      if (!mounted) return;
      setState(() {
        dados = Map<String, dynamic>.from(jsonResposta['dados'] as Map);
        carregando = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        erro = e.toString();
        carregando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (carregando) return const Center(child: CircularProgressIndicator());
    if (erro != null) {
      return _ErroPainel(erro: erro!, aoTentarNovamente: carregarPatrimonio);
    }

    final itens = (dados?['itens'] as List?) ?? [];
    final referencia = dados?['periodo']?['referencia']?.toString() ?? '---';
    final temDados = dados?['tem_dados'] == true;
    final total = dados?['patrimonio_total_fmt']?.toString() ?? r'R$ 0,00';
    final variacao = dados?['variacao_mes_fmt']?.toString() ?? r'R$ 0,00';
    final percentual = dados?['percentual_variacao_fmt']?.toString() ?? '0,0%';
    final variacaoNumero = (dados?['variacao_mes'] as num?)?.toDouble() ?? 0.0;
    final maiorAtivo = dados?['maior_ativo'] as Map?;

    return RefreshIndicator(
      onRefresh: carregarPatrimonio,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Patrimônio',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            temDados
                ? 'Último fechamento disponível · $referencia'
                : 'Nenhum fechamento de patrimônio encontrado.',
            style: const TextStyle(color: Color(0xFF64748B)),
          ),
          const SizedBox(height: 16),
          _DestaquePatrimonio(
            valor: total,
            variacao: variacao,
            percentual: percentual,
            positiva: variacaoNumero >= 0,
          ),
          const SizedBox(height: 16),
          if (maiorAtivo != null && (maiorAtivo['nome']?.toString().isNotEmpty ?? false))
            _MaiorAtivoPatrimonio(
              nome: maiorAtivo['nome']?.toString() ?? '',
              valor: maiorAtivo['valor_fmt']?.toString() ?? r'R$ 0,00',
            ),
          if (maiorAtivo != null) const SizedBox(height: 16),
          Text(
            'Ativos',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 10),
          if (!temDados || itens.isEmpty)
            const _Vazio(texto: 'Cadastre um fechamento no módulo Patrimônio web para visualizar os dados aqui.')
          else
            ...itens.map((item) => _CardAtivoPatrimonio(item: item)),
        ],
      ),
    );
  }
}

class _DestaquePatrimonio extends StatelessWidget {
  final String valor;
  final String variacao;
  final String percentual;
  final bool positiva;

  const _DestaquePatrimonio({
    required this.valor,
    required this.variacao,
    required this.percentual,
    required this.positiva,
  });

  @override
  Widget build(BuildContext context) {
    final corVariacao = positiva ? const Color(0xFFBBF7D0) : const Color(0xFFFECACA);
    final icone = positiva ? Icons.trending_up : Icons.trending_down;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF312E81),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Patrimônio total atual',
            style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            valor,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 28,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(icone, size: 18, color: corVariacao),
              const SizedBox(width: 6),
              Text(
                '${positiva ? '+' : '-'}$variacao · $percentual no período',
                style: TextStyle(color: corVariacao, fontWeight: FontWeight.w700),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MaiorAtivoPatrimonio extends StatelessWidget {
  final String nome;
  final String valor;

  const _MaiorAtivoPatrimonio({required this.nome, required this.valor});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFFEDE9FE),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.workspace_premium, color: Color(0xFF6D28D9)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Maior ativo', style: TextStyle(color: Color(0xFF64748B), fontSize: 12)),
                Text(nome, style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
          ),
          Text(valor, style: const TextStyle(color: Color(0xFF6D28D9), fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}

class _CardAtivoPatrimonio extends StatelessWidget {
  final dynamic item;
  const _CardAtivoPatrimonio({required this.item});

  @override
  Widget build(BuildContext context) {
    final nome = item['grupo']?.toString() ?? '';
    final descricao = item['descricao']?.toString() ?? '';
    final valor = item['valor_fmt']?.toString() ?? r'R$ 0,00';
    final participacao = item['participacao_fmt']?.toString() ?? '';
    final subdivisoes = (item['subdivisoes'] as List?) ?? [];

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: const Color(0xFFEDE9FE),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.account_balance, color: Color(0xFF6D28D9)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(nome, style: const TextStyle(fontWeight: FontWeight.bold)),
                    Text(
                      participacao.isEmpty ? descricao : '$descricao · $participacao',
                      style: const TextStyle(color: Color(0xFF64748B), fontSize: 12),
                    ),
                  ],
                ),
              ),
              Text(valor, style: const TextStyle(color: Color(0xFF6D28D9), fontWeight: FontWeight.bold)),
            ],
          ),
          if (subdivisoes.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 8),
            ...subdivisoes.map(
              (sub) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    const Icon(Icons.subdirectory_arrow_right, size: 16, color: Color(0xFF94A3B8)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        sub['nome']?.toString() ?? '',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
                      ),
                    ),
                    Text(
                      sub['valor_fmt']?.toString() ?? r'R$ 0,00',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _DestaqueSaldo extends StatelessWidget {
  final String valor;
  const _DestaqueSaldo({required this.valor});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(color: const Color(0xFF0F766E), borderRadius: BorderRadius.circular(24)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Saldo total disponível', style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      Text(valor, style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
    ]),
  );
}

class _CardContaAlimentacao extends StatelessWidget {
  final dynamic conta;
  const _CardContaAlimentacao({required this.conta});
  @override
  Widget build(BuildContext context) {
    final nome = conta['conta']?.toString() ?? '';
    final saldo = conta['saldo_atual_fmt']?.toString() ?? r'R$ 0,00';
    final data = conta['data_saldo']?.toString() ?? '';
    return Container(
      margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: Row(children: [
        Container(width: 44, height: 44, decoration: BoxDecoration(color: const Color(0xFFCCFBF1), borderRadius: BorderRadius.circular(14)), child: const Icon(Icons.account_balance_wallet, color: Color(0xFF0F766E))),
        const SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(nome, style: const TextStyle(fontWeight: FontWeight.bold)),
          Text(data.isEmpty ? 'Saldo atualizado' : 'Saldo em $data', style: const TextStyle(color: Color(0xFF64748B), fontSize: 12)),
        ])),
        Text(saldo, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0F766E))),
      ]),
    );
  }
}

class _MovimentacaoAlimentacao extends StatelessWidget {
  final dynamic movimentacao;
  const _MovimentacaoAlimentacao({required this.movimentacao});
  @override
  Widget build(BuildContext context) {
    final tipo = movimentacao['tipo']?.toString() ?? '';
    final entrada = tipo == 'ENTRADA';
    final descricao = movimentacao['descricao']?.toString() ?? '';
    final conta = movimentacao['conta']?.toString() ?? '';
    final data = movimentacao['data']?.toString() ?? '';
    final valor = movimentacao['valor_fmt']?.toString() ?? r'R$ 0,00';
    final cor = entrada ? const Color(0xFF16A34A) : const Color(0xFFDC2626);
    return Container(
      margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Row(children: [
        Icon(entrada ? Icons.south_west : Icons.north_east, color: cor), const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(descricao, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
          Text('$conta · $data', style: const TextStyle(color: Color(0xFF64748B), fontSize: 12)),
        ])),
        Text('${entrada ? '+' : '-'}$valor', style: TextStyle(color: cor, fontWeight: FontWeight.bold)),
      ]),
    );
  }
}

class _CardFinanceiro extends StatelessWidget {
  final dynamic card;
  const _CardFinanceiro({required this.card});
  @override
  Widget build(BuildContext context) {
    final titulo = card['titulo']?.toString() ?? '';
    final valor = card['valor_fmt']?.toString() ?? '';
    final descricao = card['descricao']?.toString() ?? '';
    final tipo = card['tipo']?.toString() ?? '';
    final cor = _corPorTipo(tipo);
    return Container(margin: const EdgeInsets.only(bottom: 14), padding: const EdgeInsets.all(18), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(22)), child: Row(children: [
      Container(width: 48, height: 48, decoration: BoxDecoration(color: cor.withAlpha(28), borderRadius: BorderRadius.circular(16)), child: Icon(_iconePorTipo(tipo), color: cor)),
      const SizedBox(width: 16), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(titulo, style: const TextStyle(color: Color(0xFF64748B), fontWeight: FontWeight.w600)), const SizedBox(height: 4),
        Text(valor, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
        if (descricao.isNotEmpty) Text(descricao, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13)),
      ])),
    ]));
  }
  Color _corPorTipo(String tipo) { switch (tipo) { case 'receita': return const Color(0xFF16A34A); case 'despesa': return const Color(0xFFDC2626); case 'saldo': return const Color(0xFF2563EB); case 'investimento': return const Color(0xFF7C3AED); case 'percentual': return const Color(0xFFEA580C); case 'alerta': return const Color(0xFFEAB308); case 'categoria': return const Color(0xFF0F766E); default: return const Color(0xFF475569); } }
  IconData _iconePorTipo(String tipo) { switch (tipo) { case 'receita': return Icons.south_west; case 'despesa': return Icons.north_east; case 'saldo': return Icons.account_balance_wallet; case 'investimento': return Icons.trending_up; case 'percentual': return Icons.pie_chart; case 'alerta': return Icons.warning_amber_rounded; case 'categoria': return Icons.sell; default: return Icons.list_alt; } }
}

class _Vazio extends StatelessWidget { final String texto; const _Vazio({required this.texto}); @override Widget build(BuildContext context) => Container(padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)), child: Text(texto, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF64748B)))); }

class _ErroPainel extends StatelessWidget {
  final String erro; final VoidCallback aoTentarNovamente;
  const _ErroPainel({required this.erro, required this.aoTentarNovamente});
  @override
  Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
    const Icon(Icons.cloud_off, size: 48, color: Color(0xFFDC2626)), const SizedBox(height: 16),
    const Text('Não foi possível carregar os dados', textAlign: TextAlign.center, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)), const SizedBox(height: 8),
    Text(erro, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF64748B), fontSize: 13)), const SizedBox(height: 20),
    FilledButton(onPressed: aoTentarNovamente, child: const Text('Tentar novamente')),
  ])));
}
