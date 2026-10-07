from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..db import consultar
from ..security import exigir_login, mascarar_cpf, decifrar

router = APIRouter(dependencies=[Depends(exigir_login)])

Periodo = Literal["semanal", "mensal", "anual"]


def _intervalo(periodo: Periodo):
    hoje = date.today()
    fim = hoje + timedelta(days=1)
    if periodo == "semanal":
        inicio = hoje - timedelta(days=6)
    elif periodo == "mensal":
        inicio = hoje.replace(day=1)
    else:
        inicio = hoje.replace(month=1, day=1)
    return inicio, fim


def _brl(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(v):
    if not v:
        return "-"
    if isinstance(v, datetime):
        v = v.date()
    return v.strftime("%d/%m/%Y")


def _par(texto, style):
    texto = str(texto if texto is not None and texto != "" else "-")
    return Paragraph(texto.replace("&", "&amp;"), style)


@router.get("/historico.pdf")
def historico_pdf(
    periodo: Periodo = Query("mensal"),
):
    inicio, fim = _intervalo(periodo)
    periodo_label = {
        "semanal": "Últimos 7 dias",
        "mensal": "Mês atual",
        "anual": "Ano atual",
    }[periodo]

    alunos = consultar(
        """
        SELECT a.id, a.nome, a.cpf_cript, a.data_nascimento, a.endereco, a.telefone,
               a.ativo, p.nome AS plano, m.vencimento, m.status
        FROM alunos a
        LEFT JOIN matriculas m ON m.id = (
          SELECT m2.id FROM matriculas m2
          WHERE m2.aluno_id=a.id ORDER BY m2.criado_em DESC LIMIT 1
        )
        LEFT JOIN planos p ON p.id=m.plano_id
        ORDER BY a.nome
        LIMIT 1000
        """
    )

    acessos = consultar(
        """
        SELECT aluno_id, data_hora, resultado, motivo
        FROM historico_acessos
        WHERE data_hora >= %s AND data_hora < %s
        ORDER BY data_hora DESC
        """,
        (inicio, fim),
    )
    pagamentos = consultar(
        """
        SELECT aluno_id, valor, data_pagamento, forma_pagamento
        FROM pagamentos
        WHERE data_pagamento >= %s AND data_pagamento < %s
        ORDER BY data_pagamento DESC
        """,
        (inicio, fim),
    )

    acessos_por_aluno = {}
    for row in acessos:
        acessos_por_aluno.setdefault(row["aluno_id"], []).append(row)
    pagamentos_por_aluno = {}
    for row in pagamentos:
        pagamentos_por_aluno.setdefault(row["aluno_id"], []).append(row)

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloRelatorio", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=20, leading=23, alignment=TA_CENTER, spaceAfter=4,
    )
    subtitulo = ParagraphStyle(
        "SubtituloRelatorio", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, leading=12, alignment=TA_CENTER, textColor=colors.HexColor("#666666"),
        spaceAfter=14,
    )
    h_aluno = ParagraphStyle(
        "Aluno", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=14, textColor=colors.HexColor("#222222"), spaceAfter=4,
    )
    normal = ParagraphStyle("NormalRel", parent=styles["Normal"], fontSize=8.5, leading=11)
    pequeno = ParagraphStyle("Pequeno", parent=normal, fontSize=7.5, leading=9.5)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title="Relatório de acesso e pagamentos",
        author="Academia - Controle de acesso",
    )

    story = [
        Paragraph("Relatório de acesso e pagamentos", titulo),
        Paragraph(
            f"{periodo_label} · {_data_br(inicio)} a {_data_br(fim - timedelta(days=1))} · Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            subtitulo,
        ),
    ]

    total_visitas = 0
    total_negados = 0
    total_pagamentos = 0
    total_recebido = 0.0

    for aluno in alunos:
        ac = acessos_por_aluno.get(aluno["id"], [])
        pg = pagamentos_por_aluno.get(aluno["id"], [])
        visitas = [r for r in ac if r["resultado"] in ("APROVADO", "LIBERADO_MANUAL")]
        negados = [r for r in ac if r["resultado"] == "NEGADO"]
        total_visitas += len(visitas)
        total_negados += len(negados)
        total_pagamentos += len(pg)
        total_recebido += sum(float(r["valor"]) for r in pg)

        try:
            cpf = mascarar_cpf(decifrar(aluno["cpf_cript"]))
        except Exception:
            cpf = "-"
        status = "Ativo" if aluno["ativo"] else "Excluído"
        if aluno["status"]:
            status += f" · matrícula {aluno['status'].lower()}"

        resumo = [
            [_par("CPF", pequeno), _par(cpf, normal), _par("Plano", pequeno), _par(aluno["plano"] or "Sem plano", normal)],
            [_par("Nascimento", pequeno), _par(_data_br(aluno["data_nascimento"]), normal), _par("Vencimento", pequeno), _par(_data_br(aluno["vencimento"]), normal)],
            [_par("Telefone", pequeno), _par(aluno["telefone"], normal), _par("Situação", pequeno), _par(status, normal)],
            [_par("Endereço", pequeno), _par(aluno["endereco"], normal), _par("Visitas no período", pequeno), _par(str(len(visitas)), normal)],
        ]
        resumo_t = Table(resumo, colWidths=[24*mm, 50*mm, 30*mm, 70*mm], hAlign="LEFT")
        resumo_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F7F6EE")),
            ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#D8D3A0")),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#E4E1C9")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))

        blocks = [
            Paragraph(aluno["nome"], h_aluno),
            resumo_t,
            Spacer(1, 5),
            Paragraph("Histórico de acessos", styles["Heading3"]),
        ]

        acessos_data = [[
            _par("Data", pequeno), _par("Hora", pequeno), _par("Resultado", pequeno), _par("Detalhe", pequeno)
        ]]
        for row in ac:
            dt = row["data_hora"]
            resultado = {"APROVADO": "Aprovado", "NEGADO": "Negado", "LIBERADO_MANUAL": "Liberação manual"}.get(row["resultado"], row["resultado"])
            acessos_data.append([
                _par(dt.strftime("%d/%m/%Y"), normal),
                _par(dt.strftime("%H:%M"), normal),
                _par(resultado, normal),
                _par(row["motivo"] or "Entrada autorizada", normal),
            ])
        if len(acessos_data) == 1:
            acessos_data.append([_par("-", normal), _par("-", normal), _par("Sem registro", normal), _par("Nenhum acesso registrado no período", normal)])
        at = Table(acessos_data, colWidths=[28*mm, 18*mm, 38*mm, 90*mm], repeatRows=1)
        at.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#23231F")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#DDDDDD")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        blocks.append(at)
        blocks.extend([Spacer(1, 6), Paragraph("Pagamentos no período", styles["Heading3"])])

        pg_data = [[_par("Data", pequeno), _par("Forma", pequeno), _par("Valor", pequeno)]]
        for row in pg:
            pg_data.append([_par(_data_br(row["data_pagamento"]), normal), _par(row["forma_pagamento"], normal), _par(_brl(row["valor"]), normal)])
        if len(pg_data) == 1:
            pg_data.append([_par("-", normal), _par("Sem registro", normal), _par("-", normal)])
        pt = Table(pg_data, colWidths=[38*mm, 70*mm, 58*mm], repeatRows=1)
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#23231F")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#DDDDDD")),
            ("ALIGN", (2,1), (2,-1), "RIGHT"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        blocks.append(pt)
        blocks.append(Spacer(1, 9))
        story.extend(blocks)

    story.extend([
        Spacer(1, 4),
        Paragraph("Resumo do período", styles["Heading2"]),
        Paragraph(
            f"Alunos: {len(alunos)} · Visitas autorizadas: {total_visitas} · Acessos negados: {total_negados} · Pagamentos: {total_pagamentos} · Total recebido: {_brl(total_recebido)}",
            normal,
        ),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawRightString(A4[0] - 12 * mm, 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)
    filename = f"relatorio-{periodo}-{date.today().isoformat()}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
