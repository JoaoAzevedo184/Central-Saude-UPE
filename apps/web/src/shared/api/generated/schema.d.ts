export interface paths {
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/registro": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Registrar
         * @description UC-001. CPF, cartão do SUS ou e-mail já cadastrados dão o mesmo 409 genérico (AM-005).
         */
        post: operations["registrar_api_v1_auth_registro_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description CPF (paciente) ou e-mail (equipe). Inexistente, senha errada e suspenso respondem igual.
         */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/trocar-senha": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Trocar Senha
         * @description Qualquer usuário autenticado. Zera `senha_temporaria` e revoga as outras sessões; a
         *     atual continua. Senha atual errada conta no limite do login (AM-020), por usuário e por IP,
         *     e o excesso responde 429 sem revogar nada.
         */
        post: operations["trocar_senha_api_v1_auth_trocar_senha_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Renovar
         * @description Rotação: o token usado é revogado e outro da mesma família é emitido. Reuso de um token
         *     já revogado indica roubo e revoga a família inteira, exceto dentro da tolerância
         *     (REFRESH_TOLERANCIA_S): aí é outra aba renovando junto e ganha um token da mesma família.
         *     Só uma reapresentação por token cabe na tolerância; a segunda revoga a família.
         */
        post: operations["renovar_api_v1_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description Revoga a família do refresh token e apaga os cookies. Idempotente: 204 mesmo sem sessão.
         */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Eu
         * @description Dados do usuário logado. A equipe recebe também as filas do seu escopo (ADR-025).
         */
        get: operations["eu_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usuarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Usuarios
         * @description Contas da equipe (sem pacientes), com as filas e unidades atribuídas.
         */
        get: operations["listar_usuarios_api_v1_admin_usuarios_get"];
        put?: never;
        /**
         * Criar Usuario
         * @description Cria ATENDENTE, GESTOR ou ADMIN com senha temporária forte, devolvida só aqui. A pessoa
         *     precisa trocá-la no primeiro acesso. GESTOR sem unidade exige `confirmar_visao_central`.
         */
        post: operations["criar_usuario_api_v1_admin_usuarios_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usuarios/{usuario_id}/redefinir-senha": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Redefinir Senha
         * @description Nova senha temporária (devolvida uma vez) e revogação de todas as sessões do usuário.
         */
        post: operations["redefinir_senha_api_v1_admin_usuarios__usuario_id__redefinir_senha_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usuarios/{usuario_id}/filas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Atribuir Filas
         * @description Substitui as filas do ATENDENTE (RF-035). Outro papel → 409.
         */
        put: operations["atribuir_filas_api_v1_admin_usuarios__usuario_id__filas_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usuarios/{usuario_id}/unidades": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Atribuir Unidades
         * @description Substitui as unidades do GESTOR (RF-035). Outro papel → 409. Lista vazia faz o gestor
         *     ver a central inteira (ADR-025) e exige `confirmar_visao_central: true`.
         */
        put: operations["atribuir_unidades_api_v1_admin_usuarios__usuario_id__unidades_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/filas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Filas
         * @description Todas as filas, com unidade e especialidade, para a tela de atribuição.
         */
        get: operations["listar_filas_api_v1_admin_filas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usuarios/{usuario_id}/suspender": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Suspender
         * @description Grava a suspensão e revoga todas as sessões do usuário. O access token que ainda não
         *     venceu deixa de valer na próxima requisição, porque `usuario_da_sessao` relê a situação.
         */
        post: operations["suspender_api_v1_admin_usuarios__usuario_id__suspender_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usuarios/{usuario_id}/reativar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reativar
         * @description Volta a ATIVO. `suspenso_em` e `motivo_suspensao` ficam como registro (ADR-028).
         */
        post: operations["reativar_api_v1_admin_usuarios__usuario_id__reativar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/filas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Filas
         * @description Filas ativas, com a elegibilidade do paciente (RN-017). `total` é o das filas ativas,
         *     nunca contagem de pessoas.
         */
        get: operations["listar_filas_api_v1_filas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/filas/{fila_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Detalhar Fila
         * @description Fila e as perguntas de origem PACIENTE do protocolo, sem peso nem pontos.
         */
        get: operations["detalhar_fila_api_v1_filas__fila_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/solicitacoes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar
         * @description Solicitações do paciente. `encerradas` alimenta o "Histórico de atendimentos".
         *
         *     Uma consulta traz o agendamento ativo de cada item (sem N+1), mais a contagem do filtro.
         */
        get: operations["listar_api_v1_solicitacoes_get"];
        put?: never;
        /**
         * Criar
         * @description UC-002: cria a solicitação em EM_ANALISE, com a nota das respostas (RN-006).
         */
        post: operations["criar_api_v1_solicitacoes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/solicitacoes/{solicitacao_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Detalhar
         * @description Status, fila e linha do tempo só com os eventos visíveis ao paciente (RN-007).
         */
        get: operations["detalhar_api_v1_solicitacoes__solicitacao_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/solicitacoes/{solicitacao_id}/cancelar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancelar
         * @description Cancelamento ("não vou precisar"): EM_ANALISE, NA_FILA, EM_PROPOSTA ou AGENDADA.
         *
         *     Com proposta ou consulta ativa, o agendamento é cancelado junto, só antes do início da
         *     vaga; a vaga fica livre e o Worker a oferece ao próximo (RN-005). Outros estados → 409.
         *     Travas: solicitação, depois agendamento (a vaga só é lida).
         */
        post: operations["cancelar_api_v1_solicitacoes__solicitacao_id__cancelar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agendamentos/{agendamento_id}/confirmar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirmar
         * @description UC-004: PROPOSTO → CONFIRMADO e solicitação AGENDADA, só antes de `expira_em`.
         */
        post: operations["confirmar_api_v1_agendamentos__agendamento_id__confirmar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agendamentos/{agendamento_id}/recusar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Recusar
         * @description UC-005 ("esta data não serve"): só PROPOSTO. A vaga fica livre para o próximo.
         */
        post: operations["recusar_api_v1_agendamentos__agendamento_id__recusar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/filas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Filas
         * @description Filas do escopo, com a contagem de solicitações por status.
         */
        get: operations["listar_filas_api_v1_equipe_filas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/filas/{fila_id}/solicitacoes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Painel
         * @description Painel da fila (RF-031, RF-032). A posição vem de `ROW_NUMBER()` sobre todas as
         *     solicitações NA_FILA da fila, antes da paginação, na ordem de `ordenar_fila()`.
         */
        get: operations["painel_api_v1_equipe_filas__fila_id__solicitacoes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/solicitacoes/{solicitacao_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Detalhar
         * @description Detalhe com respostas (critério, valor, pontos), nota e histórico completo.
         */
        get: operations["detalhar_api_v1_equipe_solicitacoes__solicitacao_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/filas/{fila_id}/criterios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Criterios Da Equipe
         * @description Critérios ativos de origem REGULACAO e EQUIPE da fila, para montar o formulário de
         *     `PUT /equipe/solicitacoes/{id}/respostas`. Sem peso, fator nem pontos: a matriz de acesso
         *     não os libera para a leitura da equipe. Sem auditoria: não traz dado de paciente.
         */
        get: operations["criterios_da_equipe_api_v1_equipe_filas__fila_id__criterios_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/solicitacoes/{solicitacao_id}/classificar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Classificar
         * @description Classificação de risco, simulando a regulação. EM_ANALISE → NA_FILA; em NA_FILA só
         *     reclassifica, com motivo obrigatório. Outros estados → 409.
         */
        post: operations["classificar_api_v1_equipe_solicitacoes__solicitacao_id__classificar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/solicitacoes/{solicitacao_id}/respostas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Responder Criterios
         * @description Critérios de origem REGULACAO ou EQUIPE; a nota é recalculada por `calcular_nota()`.
         *     Na fila, nota diferente grava RECLASSIFICADA (só equipe).
         */
        put: operations["responder_criterios_api_v1_equipe_solicitacoes__solicitacao_id__respostas_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/filas/{fila_id}/agendamentos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Agendamentos Do Dia
         * @description Agenda do dia (UC-008): hora, paciente abreviado, status e se a presença foi registrada.
         *     `data` é o dia em Recife. Leitura auditada.
         */
        get: operations["agendamentos_do_dia_api_v1_equipe_filas__fila_id__agendamentos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/agendamentos/{agendamento_id}/presenca": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Presenca
         * @description UC-008. Compareceu: a partir do início da vaga, REALIZADO e solicitação ATENDIDA.
         *     Faltou: só depois da tolerância (RN-013), FALTOU e solicitação no fim da fila (RN-014).
         *     Só de CONFIRMADO; fora do escopo → 404.
         */
        post: operations["presenca_api_v1_equipe_agendamentos__agendamento_id__presenca_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/equipe/filas/{fila_id}/vagas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Painel De Vagas
         * @description Vagas de `de` a `ate` (dias em Recife, inclusivos, até 31 dias) com a situação
         *     derivada por `situacao_da_vaga()`. Nada é gravado. Leitura auditada.
         */
        get: operations["painel_de_vagas_api_v1_equipe_filas__fila_id__vagas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/avisos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar
         * @description Mais recentes primeiro.
         */
        get: operations["listar_api_v1_avisos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/avisos/contagem": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Contagem
         * @description Para o sino do menu.
         */
        get: operations["contagem_api_v1_avisos_contagem_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/avisos/lidos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Marcar Todos */
        post: operations["marcar_todos_api_v1_avisos_lidos_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/avisos/{aviso_id}/lido": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Marcar Lido
         * @description Idempotente: já lido continua com a data da primeira leitura.
         */
        post: operations["marcar_lido_api_v1_avisos__aviso_id__lido_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/termos/vigente": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Vigente
         * @description Versão em `TERMO_VERSAO_ATUAL` e o texto de `app/termos/<versao>.md`. Público: o
         *     cadastro mostra o termo antes de haver sessão. É a versão que `POST /auth/registro` aceita.
         */
        get: operations["vigente_api_v1_termos_vigente_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AgendamentoDoDia */
        AgendamentoDoDia: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Solicitacao Id
             * Format: uuid
             */
            solicitacao_id: string;
            /**
             * Inicio
             * Format: date-time
             */
            inicio: string;
            /**
             * Fim
             * Format: date-time
             */
            fim: string;
            /** Profissional */
            profissional: string;
            /** Paciente Nome */
            paciente_nome: string;
            status: components["schemas"]["StatusAgendamento"];
            /** Presenca Registrada */
            presenca_registrada: boolean;
        };
        /** AgendamentoPaciente */
        AgendamentoPaciente: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "PROPOSTO" | "CONFIRMADO";
            /**
             * Inicio
             * Format: date-time
             */
            inicio: string;
            /** Expira Em */
            expira_em: string | null;
            unidade: components["schemas"]["UnidadeSaida"];
            /** Profissional */
            profissional: string;
            /**
             * Fim
             * Format: date-time
             */
            fim: string;
            /** Endereco */
            endereco: string | null;
        };
        /**
         * AgendamentoResumo
         * @description Proposta (com `expira_em`) ou consulta confirmada. Horários no fuso de Recife.
         */
        AgendamentoResumo: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "PROPOSTO" | "CONFIRMADO";
            /**
             * Inicio
             * Format: date-time
             */
            inicio: string;
            /** Expira Em */
            expira_em: string | null;
            unidade: components["schemas"]["UnidadeSaida"];
            /** Profissional */
            profissional: string;
        };
        /** AvisoSaida */
        AvisoSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            tipo: components["schemas"]["TipoAviso"];
            /** Titulo */
            titulo: string;
            /** Corpo */
            corpo: string;
            /** Solicitacao Id */
            solicitacao_id: string | null;
            /**
             * Criado Em
             * Format: date-time
             */
            criado_em: string;
            /** Lido Em */
            lido_em: string | null;
        };
        /**
         * CancelamentoEntrada
         * @description Sem texto livre: só o código (`MOTIVOS_CANCELAMENTO`), validado pelo domínio.
         */
        CancelamentoEntrada: {
            motivo_codigo: components["schemas"]["MotivoCancelamento"];
        };
        /** ClassificacaoEntrada */
        ClassificacaoEntrada: {
            classificacao_risco: components["schemas"]["ClassificacaoRisco"];
            /** Motivo */
            motivo?: string | null;
        };
        /**
         * ClassificacaoRisco
         * @enum {string}
         */
        ClassificacaoRisco: "VERMELHO" | "AMARELO" | "VERDE";
        /** ContagemSaida */
        ContagemSaida: {
            /** Nao Lidos */
            nao_lidos: number;
        };
        /**
         * CriterioEquipeSaida
         * @description Pergunta que a equipe responde para montar o formulário. Sem peso, fator nem pontos.
         */
        CriterioEquipeSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Codigo */
            codigo: string;
            /** Descricao */
            descricao: string;
            tipo: components["schemas"]["TipoCriterio"];
            /**
             * Origem
             * @enum {string}
             */
            origem: "REGULACAO" | "EQUIPE";
            /** Opcoes */
            opcoes: string[] | null;
            /** Faixas */
            faixas: components["schemas"]["FaixaCriterio"][] | null;
        };
        /**
         * CriterioPacienteSaida
         * @description Sem peso, fatores nem pontos: o paciente só vê a pergunta.
         */
        CriterioPacienteSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Codigo */
            codigo: string;
            /** Descricao */
            descricao: string;
            tipo: components["schemas"]["TipoCriterio"];
            /** Opcoes */
            opcoes: string[] | null;
        };
        /** ErroDeCampo */
        ErroDeCampo: {
            /** Loc */
            loc: (string | number)[];
            /** Msg */
            msg: string;
            /** Type */
            type: string;
        };
        /** EspecialidadeResumo */
        EspecialidadeResumo: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
        };
        /** EspecialidadeSaida */
        EspecialidadeSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
        };
        /**
         * EuSaida
         * @description Para o paciente, nunca posição nem tamanho da fila (ADR-007).
         *
         *     Todas as chaves vêm sempre. `nome` é `null` na equipe (`usuario` não tem nome) e `filas`
         *     é `null` no paciente; na equipe, `filas` traz o escopo (ADR-025), `[]` se não houver.
         */
        EuSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            papel: components["schemas"]["Papel"];
            /** Nome */
            nome: string | null;
            /** Filas */
            filas: string[] | null;
            /** Trocar Senha */
            trocar_senha?: true | null;
        };
        /** EventoEquipe */
        EventoEquipe: {
            tipo: components["schemas"]["TipoEventoLinhaDoTempo"];
            status_anterior: components["schemas"]["StatusSolicitacao"] | null;
            status_novo: components["schemas"]["StatusSolicitacao"] | null;
            /** Motivo */
            motivo: string | null;
            /** Visivel Paciente */
            visivel_paciente: boolean;
            /** Ator Usuario Id */
            ator_usuario_id: string | null;
            /**
             * Ocorrido Em
             * Format: date-time
             */
            ocorrido_em: string;
        };
        /**
         * EventoPaciente
         * @description Só o dia, sem hora: a hora de ENTROU_NA_FILA revelaria `data_entrada_fila` (ADR-007).
         */
        EventoPaciente: {
            tipo: components["schemas"]["TipoEventoLinhaDoTempo"];
            /**
             * Data
             * Format: date
             */
            data: string;
            /** Motivo */
            motivo: string | null;
        };
        /**
         * FaixaCriterio
         * @description Faixa de um critério `NUMERO` (limites inclusivos e opcionais). Sem o fator: o peso fica
         *     com o protocolo.
         */
        FaixaCriterio: {
            /** Min */
            min?: number | null;
            /** Max */
            max?: number | null;
        };
        /** FilaAdmin */
        FilaAdmin: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
            /** Ativa */
            ativa: boolean;
            unidade: components["schemas"]["UnidadeResumo"];
            especialidade: components["schemas"]["EspecialidadeResumo"];
        };
        /** FilaDetalheSaida */
        FilaDetalheSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
            /** Descricao Paciente */
            descricao_paciente: string;
            unidade: components["schemas"]["UnidadeSaida"];
            especialidade: components["schemas"]["EspecialidadeSaida"];
            /** Elegivel */
            elegivel: boolean;
            /** Motivo Inelegivel */
            motivo_inelegivel: string | null;
            /** Criterios */
            criterios: components["schemas"]["CriterioPacienteSaida"][];
        };
        /** FilaEquipeSaida */
        FilaEquipeSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
            /** Unidade Sigla */
            unidade_sigla: string;
            /** Especialidade */
            especialidade: string;
            /** Ativa */
            ativa: boolean;
            /** Contagem Por Status */
            contagem_por_status: {
                [key: string]: number;
            };
        };
        /** FilaResumo */
        FilaResumo: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
            unidade: components["schemas"]["UnidadeSaida"];
        };
        /** FilaSaida */
        FilaSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nome */
            nome: string;
            /** Descricao Paciente */
            descricao_paciente: string;
            unidade: components["schemas"]["UnidadeSaida"];
            especialidade: components["schemas"]["EspecialidadeSaida"];
            /** Elegivel */
            elegivel: boolean;
            /** Motivo Inelegivel */
            motivo_inelegivel: string | null;
        };
        /** FilasEntrada */
        FilasEntrada: {
            /** Fila Ids */
            fila_ids: string[];
        };
        /** ItemPainel */
        ItemPainel: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            status: components["schemas"]["StatusSolicitacao"];
            /** Posicao */
            posicao: number | null;
            classificacao_risco: components["schemas"]["ClassificacaoRisco"] | null;
            /** Nota */
            nota: number;
            /** Data Entrada Fila */
            data_entrada_fila: string | null;
            /** Paciente Nome */
            paciente_nome: string;
            /** Paciente Cpf */
            paciente_cpf: string;
            ultima_mudanca: components["schemas"]["UltimaMudanca"] | null;
        };
        /** LoginEntrada */
        LoginEntrada: {
            /**
             * Identificador
             * @description CPF ou e-mail
             */
            identificador: string;
            /**
             * Senha
             * Format: password
             */
            senha: string;
        };
        /**
         * LoginSaida
         * @description `trocar_senha` só aparece (`true`) para conta com senha temporária: o frontend deve levar
         *     a pessoa à troca, porque o resto da API responde 403 até lá.
         */
        LoginSaida: {
            papel: components["schemas"]["Papel"];
            /**
             * Expira Em
             * Format: date-time
             */
            expira_em: string;
            /** Trocar Senha */
            trocar_senha?: true | null;
        };
        /**
         * MotivoCancelamento
         * @enum {string}
         */
        MotivoCancelamento: "NAO_PRECISO_MAIS" | "CONSEGUI_EM_OUTRO_LUGAR" | "DIFICULDADE_DE_DESLOCAMENTO" | "CONFLITO_DE_HORARIO" | "OUTRO";
        /**
         * OrigemCriterio
         * @enum {string}
         */
        OrigemCriterio: "PACIENTE" | "REGULACAO" | "EQUIPE";
        /** PaginaAvisos */
        PaginaAvisos: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["AvisoSaida"][];
        };
        /** PaginaFilas */
        PaginaFilas: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["FilaSaida"][];
        };
        /** PaginaFilasEquipe */
        PaginaFilasEquipe: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["FilaEquipeSaida"][];
        };
        /** PaginaSolicitacoes */
        PaginaSolicitacoes: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["SolicitacaoItem"][];
        };
        /** Pagina[FilaAdmin] */
        Pagina_FilaAdmin_: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["FilaAdmin"][];
        };
        /** Pagina[UsuarioAdmin] */
        Pagina_UsuarioAdmin_: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["UsuarioAdmin"][];
        };
        /** PainelSaida */
        PainelSaida: {
            /** Total */
            total: number;
            /** Itens */
            itens: components["schemas"]["ItemPainel"][];
        };
        /** PainelVagasSaida */
        PainelVagasSaida: {
            /** Total */
            total: number;
            /** Sem Proposta */
            sem_proposta: number;
            /** Itens */
            itens: components["schemas"]["VagaPainel"][];
        };
        /**
         * Papel
         * @enum {string}
         */
        Papel: "PACIENTE" | "ATENDENTE" | "GESTOR" | "ADMIN";
        /** PresencaEntrada */
        PresencaEntrada: {
            /** Compareceu */
            compareceu: boolean;
        };
        /**
         * Problema
         * @description Corpo de toda resposta de erro (`Content-Type: application/problem+json`).
         */
        Problema: {
            /** Type */
            type: string;
            /** Title */
            title: string;
            /** Status */
            status: number;
            /**
             * Detail
             * @default null
             */
            detail: string | null;
            /**
             * Instance
             * @default null
             */
            instance: string | null;
            /**
             * Errors
             * @default null
             */
            errors: components["schemas"]["ErroDeCampo"][] | null;
        };
        /**
         * RegistroEntrada
         * @description AM-013: sem papel, situação, classificação de risco nem IDs; campo extra → 422.
         */
        RegistroEntrada: {
            /** Nome */
            nome: string;
            /** Cpf */
            cpf: string;
            /** Cns */
            cns: string;
            /**
             * Data Nascimento
             * Format: date
             */
            data_nascimento: string;
            /** Sexo */
            sexo?: ("FEMININO" | "MASCULINO") | null;
            /** Municipio */
            municipio: string;
            /** Telefone */
            telefone: string;
            /** Email */
            email?: string | null;
            /**
             * Senha
             * Format: password
             */
            senha: string;
            /**
             * Aceite Termo
             * @constant
             */
            aceite_termo: true;
            /** Versao Termo */
            versao_termo: string;
            /**
             * Aceite Lembrete Email
             * @default false
             */
            aceite_lembrete_email: boolean;
        };
        /** RespostaEntrada */
        RespostaEntrada: {
            /**
             * Criterio Id
             * Format: uuid
             */
            criterio_id: string;
            /** Valor */
            valor: boolean | number | string;
        };
        /** RespostaEquipeSaida */
        RespostaEquipeSaida: {
            /**
             * Criterio Id
             * Format: uuid
             */
            criterio_id: string;
            /** Codigo */
            codigo: string;
            /** Descricao */
            descricao: string;
            origem: components["schemas"]["OrigemCriterio"];
            /** Valor */
            valor: unknown;
            /** Pontos */
            pontos: number;
        };
        /** RespostaPaciente */
        RespostaPaciente: {
            /** Descricao */
            descricao: string;
            /** Valor */
            valor: boolean | number | string;
        };
        /** RespostasEntrada */
        RespostasEntrada: {
            /** Respostas */
            respostas: components["schemas"]["RespostaEntrada"][];
        };
        /**
         * SenhaTemporariaSaida
         * @description A senha aparece só aqui, uma vez. Não há como lê-la depois.
         */
        SenhaTemporariaSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Senha Temporaria */
            senha_temporaria: string;
        };
        /**
         * SessaoSaida
         * @description Os tokens vão só em cookies httpOnly (ADR-003); o corpo não traz token.
         */
        SessaoSaida: {
            papel: components["schemas"]["Papel"];
            /**
             * Expira Em
             * Format: date-time
             */
            expira_em: string;
        };
        /**
         * SituacaoVaga
         * @enum {string}
         */
        SituacaoVaga: "LIVRE" | "LIVRE_SEM_PROPOSTA" | "PROPOSTA" | "CONFIRMADA" | "BLOQUEADA" | "ENCERRADA";
        /** SolicitacaoDetalhe */
        SolicitacaoDetalhe: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            status: components["schemas"]["StatusSolicitacao"];
            fila: components["schemas"]["FilaResumo"];
            /**
             * Data Pedido
             * Format: date
             */
            data_pedido: string;
            /**
             * Criada Em
             * Format: date-time
             */
            criada_em: string;
            turno_preferido: components["schemas"]["Turno"];
            /** Origem Encaminhamento */
            origem_encaminhamento: string | null;
            /** Respostas */
            respostas: components["schemas"]["RespostaPaciente"][];
            /** Linha Do Tempo */
            linha_do_tempo: components["schemas"]["EventoPaciente"][];
            agendamento_ativo: components["schemas"]["AgendamentoPaciente"] | null;
        };
        /**
         * SolicitacaoEntrada
         * @description AM-013: sem status, risco, nota nem pontos; o servidor calcula.
         */
        SolicitacaoEntrada: {
            /**
             * Fila Id
             * Format: uuid
             */
            fila_id: string;
            /** @default QUALQUER */
            turno_preferido: components["schemas"]["Turno"];
            /** Origem Encaminhamento */
            origem_encaminhamento: string;
            /** Respostas */
            respostas?: components["schemas"]["RespostaEntrada"][];
        };
        /** SolicitacaoEquipeSaida */
        SolicitacaoEquipeSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            status: components["schemas"]["StatusSolicitacao"];
            /**
             * Fila Id
             * Format: uuid
             */
            fila_id: string;
            /** Paciente Nome */
            paciente_nome: string;
            /** Paciente Cpf */
            paciente_cpf: string;
            classificacao_risco: components["schemas"]["ClassificacaoRisco"] | null;
            /** Nota */
            nota: number;
            /** Data Entrada Fila */
            data_entrada_fila: string | null;
            /**
             * Data Pedido
             * Format: date
             */
            data_pedido: string;
            turno_preferido: components["schemas"]["Turno"];
            /** Origem Encaminhamento */
            origem_encaminhamento: string | null;
            /** Respostas */
            respostas: components["schemas"]["RespostaEquipeSaida"][];
            /** Historico */
            historico: components["schemas"]["EventoEquipe"][];
        };
        /**
         * SolicitacaoItem
         * @description Item de "Meus atendimentos": o resumo da solicitação e do agendamento ativo.
         */
        SolicitacaoItem: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            status: components["schemas"]["StatusSolicitacao"];
            fila: components["schemas"]["FilaResumo"];
            /**
             * Data Pedido
             * Format: date
             */
            data_pedido: string;
            /**
             * Criada Em
             * Format: date-time
             */
            criada_em: string;
            agendamento_ativo: components["schemas"]["AgendamentoResumo"] | null;
        };
        /**
         * StatusAgendamento
         * @enum {string}
         */
        StatusAgendamento: "PROPOSTO" | "CONFIRMADO" | "CANCELADO" | "EXPIRADO" | "REALIZADO" | "FALTOU";
        /**
         * StatusSolicitacao
         * @enum {string}
         */
        StatusSolicitacao: "EM_ANALISE" | "NA_FILA" | "EM_PROPOSTA" | "AGENDADA" | "ATENDIDA" | "CANCELADA";
        /** SuspensaoEntrada */
        SuspensaoEntrada: {
            /** Motivo */
            motivo: string;
        };
        /** TermoSaida */
        TermoSaida: {
            /** Versao */
            versao: string;
            /** Texto */
            texto: string;
        };
        /**
         * TipoAviso
         * @enum {string}
         */
        TipoAviso: "AGENDAMENTO_CANCELADO" | "AGENDAMENTO_CONFIRMADO" | "ATENDIMENTO_REGISTRADO" | "FALTA_REGISTRADA" | "PROPOSTA_ENVIADA" | "PROPOSTA_EXPIRADA" | "PROPOSTA_RECUSADA" | "SOLICITACAO_CANCELADA" | "SOLICITACAO_CRIADA" | "SOLICITACAO_NA_FILA" | "LEMBRETE";
        /**
         * TipoCriterio
         * @enum {string}
         */
        TipoCriterio: "SIM_NAO" | "NUMERO" | "OPCAO";
        /**
         * TipoEventoLinhaDoTempo
         * @enum {string}
         */
        TipoEventoLinhaDoTempo: "CRIADA" | "CLASSIFICADA" | "ENTROU_NA_FILA" | "PROPOSTA_ENVIADA" | "CONFIRMADA" | "RECUSADA" | "PROPOSTA_EXPIRADA" | "FALTOU" | "ATENDIDA" | "CANCELADA" | "REENTROU_NA_FILA" | "RECLASSIFICADA";
        /** TrocaSenhaEntrada */
        TrocaSenhaEntrada: {
            /**
             * Senha Atual
             * Format: password
             */
            senha_atual: string;
            /**
             * Senha Nova
             * Format: password
             */
            senha_nova: string;
        };
        /**
         * Turno
         * @enum {string}
         */
        Turno: "MANHA" | "TARDE" | "QUALQUER";
        /**
         * UltimaMudanca
         * @description Sem motivo: texto livre da reclassificação fica só no detalhe, que é auditado.
         */
        UltimaMudanca: {
            tipo: components["schemas"]["TipoEventoLinhaDoTempo"];
            /**
             * Ocorrido Em
             * Format: date-time
             */
            ocorrido_em: string;
        };
        /** UnidadeResumo */
        UnidadeResumo: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Sigla */
            sigla: string;
        };
        /** UnidadeSaida */
        UnidadeSaida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Sigla */
            sigla: string;
            /** Nome */
            nome: string;
        };
        /** UnidadesEntrada */
        UnidadesEntrada: {
            /** Unidade Ids */
            unidade_ids: string[];
            /**
             * Confirmar Visao Central
             * @default false
             */
            confirmar_visao_central: boolean;
        };
        /**
         * UsuarioAdmin
         * @description `filas` só para ATENDENTE e `unidades` só para GESTOR; gestor sem unidade vê a central.
         */
        UsuarioAdmin: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Email */
            email: string | null;
            papel: components["schemas"]["Papel"];
            /**
             * Situacao
             * @enum {string}
             */
            situacao: "ATIVO" | "SUSPENSO";
            /** Senha Temporaria */
            senha_temporaria: boolean;
            /** Filas */
            filas: string[];
            /** Unidades */
            unidades: string[];
        };
        /**
         * UsuarioEntrada
         * @description Papel só da equipe. `unidade_ids` vale só para GESTOR (outro papel → 422).
         */
        UsuarioEntrada: {
            /** Email */
            email: string;
            /**
             * Papel
             * @enum {string}
             */
            papel: "ATENDENTE" | "GESTOR" | "ADMIN";
            /** Unidade Ids */
            unidade_ids?: string[] | null;
            /**
             * Confirmar Visao Central
             * @default false
             */
            confirmar_visao_central: boolean;
        };
        /** VagaPainel */
        VagaPainel: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Inicio
             * Format: date-time
             */
            inicio: string;
            /**
             * Fim
             * Format: date-time
             */
            fim: string;
            /** Profissional */
            profissional: string;
            situacao: components["schemas"]["SituacaoVaga"];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    registrar_api_v1_auth_registro_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegistroEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessaoSaida"];
                };
            };
            /** @description Conflict: `/problemas/cadastro-nao-concluido` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Too Many Requests: `/problemas/muitas-tentativas` */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/credenciais-invalidas` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Too Many Requests: `/problemas/muitas-tentativas` */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    trocar_senha_api_v1_auth_trocar_senha_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TrocaSenhaEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/csrf-invalido` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Too Many Requests: `/problemas/muitas-tentativas` */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    renovar_api_v1_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessaoSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/csrf-invalido` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Forbidden: `/problemas/csrf-invalido` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    eu_api_v1_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EuSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    listar_usuarios_api_v1_admin_usuarios_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                papel?: ("ATENDENTE" | "GESTOR" | "ADMIN") | null;
                situacao?: ("ATIVO" | "SUSPENSO") | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Pagina_UsuarioAdmin_"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    criar_usuario_api_v1_admin_usuarios_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UsuarioEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SenhaTemporariaSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/email-ja-cadastrado`, `/problemas/visao-central-nao-confirmada` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    redefinir_senha_api_v1_admin_usuarios__usuario_id__redefinir_senha_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                usuario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SenhaTemporariaSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/operacao-nao-permitida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    atribuir_filas_api_v1_admin_usuarios__usuario_id__filas_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                usuario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FilasEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/operacao-nao-permitida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    atribuir_unidades_api_v1_admin_usuarios__usuario_id__unidades_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                usuario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UnidadesEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/operacao-nao-permitida`, `/problemas/visao-central-nao-confirmada` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    listar_filas_api_v1_admin_filas_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Pagina_FilaAdmin_"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    suspender_api_v1_admin_usuarios__usuario_id__suspender_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                usuario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SuspensaoEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida`, `/problemas/operacao-nao-permitida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    reativar_api_v1_admin_usuarios__usuario_id__reativar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                usuario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    listar_filas_api_v1_filas_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginaFilas"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    detalhar_fila_api_v1_filas__fila_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                fila_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FilaDetalheSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    listar_api_v1_solicitacoes_get: {
        parameters: {
            query?: {
                situacao?: ("abertas" | "encerradas") | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginaSolicitacoes"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    criar_api_v1_solicitacoes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitacaoEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoDetalhe"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/sem-consentimento`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/nao-elegivel`, `/problemas/solicitacao-duplicada` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    detalhar_api_v1_solicitacoes__solicitacao_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                solicitacao_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoDetalhe"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    cancelar_api_v1_solicitacoes__solicitacao_id__cancelar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                solicitacao_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CancelamentoEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoDetalhe"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    confirmar_api_v1_agendamentos__agendamento_id__confirmar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agendamento_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoDetalhe"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida`, `/problemas/proposta-expirada` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    recusar_api_v1_agendamentos__agendamento_id__recusar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agendamento_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoDetalhe"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida`, `/problemas/proposta-expirada` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    listar_filas_api_v1_equipe_filas_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginaFilasEquipe"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    painel_api_v1_equipe_filas__fila_id__solicitacoes_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["StatusSolicitacao"] | null;
                ordenacao?: "prioridade" | "chegada";
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                fila_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PainelSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    detalhar_api_v1_equipe_solicitacoes__solicitacao_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                solicitacao_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoEquipeSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    criterios_da_equipe_api_v1_equipe_filas__fila_id__criterios_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                fila_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CriterioEquipeSaida"][];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    classificar_api_v1_equipe_solicitacoes__solicitacao_id__classificar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                solicitacao_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClassificacaoEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoEquipeSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    responder_criterios_api_v1_equipe_solicitacoes__solicitacao_id__respostas_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                solicitacao_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RespostasEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoEquipeSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    agendamentos_do_dia_api_v1_equipe_filas__fila_id__agendamentos_get: {
        parameters: {
            query: {
                data: string;
            };
            header?: never;
            path: {
                fila_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgendamentoDoDia"][];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    presenca_api_v1_equipe_agendamentos__agendamento_id__presenca_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agendamento_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PresencaEntrada"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SolicitacaoEquipeSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Conflict: `/problemas/transicao-invalida`, `/problemas/tolerancia-nao-encerrada` */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    painel_de_vagas_api_v1_equipe_filas__fila_id__vagas_get: {
        parameters: {
            query: {
                de: string;
                ate: string;
            };
            header?: never;
            path: {
                fila_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PainelVagasSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/sem-permissao`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    listar_api_v1_avisos_get: {
        parameters: {
            query?: {
                somente_nao_lidos?: boolean;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginaAvisos"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    contagem_api_v1_avisos_contagem_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContagemSaida"];
                };
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    marcar_todos_api_v1_avisos_lidos_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    marcar_lido_api_v1_avisos__aviso_id__lido_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                aviso_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized: `/problemas/nao-autenticado` */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Forbidden: `/problemas/csrf-invalido`, `/problemas/troca-de-senha-obrigatoria` */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problema"];
                };
            };
        };
    };
    vigente_api_v1_termos_vigente_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TermoSaida"];
                };
            };
        };
    };
}
