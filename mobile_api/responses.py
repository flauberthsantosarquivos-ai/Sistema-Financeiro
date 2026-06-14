def resposta_sucesso(dados=None, mensagem="Operação realizada com sucesso"):
    """
    Padroniza respostas de sucesso para a API mobile.
    """

    return {
        "sucesso": True,
        "mensagem": mensagem,
        "dados": dados if dados is not None else {},
    }


def resposta_erro(mensagem="Não foi possível concluir a operação", detalhes=None):
    """
    Padroniza respostas de erro para a API mobile.
    """

    return {
        "sucesso": False,
        "mensagem": mensagem,
        "detalhes": detalhes if detalhes is not None else {},
    }