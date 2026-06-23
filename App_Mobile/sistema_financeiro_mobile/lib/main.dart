import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const SistemaFinanceiroApp());
}

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
      home: const PainelGerencialPage(),
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

  final String urlApi =
      'http://192.168.100.235:8001/api/mobile/painel-gerencial?ano=2026&mes=6';

  @override
  void initState() {
    super.initState();
    carregarPainel();
  }

  Future<void> carregarPainel() async {
    setState(() {
      carregando = true;
      erro = null;
    });

    try {
      final resposta = await http.get(Uri.parse(urlApi));

      if (resposta.statusCode != 200) {
        throw Exception('Erro HTTP ${resposta.statusCode}');
      }

      final jsonResposta = jsonDecode(resposta.body);

      if (jsonResposta['sucesso'] != true) {
        throw Exception(jsonResposta['mensagem'] ?? 'Erro ao carregar dados');
      }

      setState(() {
        dados = jsonResposta['dados'];
        carregando = false;
      });
    } catch (e) {
      setState(() {
        erro = e.toString();
        carregando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final cards = (dados?['cards'] as List?) ?? [];
    final periodo = dados?['periodo']?['referencia'] ?? '---';

    return Scaffold(
      backgroundColor: const Color(0xFFF1F5F9),
      appBar: AppBar(
        title: const Text('Sistema Financeiro'),
        centerTitle: false,
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
      ),
      body: carregando
          ? const Center(child: CircularProgressIndicator())
          : erro != null
              ? _ErroPainel(
                  erro: erro!,
                  aoTentarNovamente: carregarPainel,
                )
              : RefreshIndicator(
                  onRefresh: carregarPainel,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Text(
                        'Painel Gerencial',
                        style:
                            Theme.of(context).textTheme.headlineSmall?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Período: $periodo',
                        style: const TextStyle(
                          color: Color(0xFF64748B),
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(height: 20),
                      ...cards.map((card) {
                        return _CardFinanceiro(card: card);
                      }).toList(),
                    ],
                  ),
                ),
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
    final icone = _iconePorTipo(tipo);

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(12),
            blurRadius: 14,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: cor.withAlpha(28),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Icon(
              icone,
              color: cor,
              size: 26,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  titulo,
                  style: const TextStyle(
                    color: Color(0xFF64748B),
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  valor,
                  style: const TextStyle(
                    color: Color(0xFF0F172A),
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (descricao.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    descricao,
                    style: const TextStyle(
                      color: Color(0xFF94A3B8),
                      fontSize: 13,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Color _corPorTipo(String tipo) {
    switch (tipo) {
      case 'receita':
        return const Color(0xFF16A34A);
      case 'despesa':
        return const Color(0xFFDC2626);
      case 'saldo':
        return const Color(0xFF2563EB);
      case 'investimento':
        return const Color(0xFF7C3AED);
      case 'percentual':
        return const Color(0xFFEA580C);
      case 'alerta':
        return const Color(0xFFEAB308);
      case 'categoria':
        return const Color(0xFF0F766E);
      default:
        return const Color(0xFF475569);
    }
  }

  IconData _iconePorTipo(String tipo) {
    switch (tipo) {
      case 'receita':
        return Icons.south_west;
      case 'despesa':
        return Icons.north_east;
      case 'saldo':
        return Icons.account_balance_wallet;
      case 'investimento':
        return Icons.trending_up;
      case 'percentual':
        return Icons.pie_chart;
      case 'alerta':
        return Icons.warning_amber_rounded;
      case 'categoria':
        return Icons.sell;
      default:
        return Icons.list_alt;
    }
  }
}

class _ErroPainel extends StatelessWidget {
  final String erro;
  final VoidCallback aoTentarNovamente;

  const _ErroPainel({
    required this.erro,
    required this.aoTentarNovamente,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.cloud_off,
              size: 48,
              color: Color(0xFFDC2626),
            ),
            const SizedBox(height: 16),
            const Text(
              'Não foi possível carregar o painel',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              erro,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFF64748B),
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: aoTentarNovamente,
              child: const Text('Tentar novamente'),
            ),
          ],
        ),
      ),
    );
  }
}