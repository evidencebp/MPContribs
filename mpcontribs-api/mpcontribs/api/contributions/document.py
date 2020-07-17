# -*- coding: utf-8 -*-
from datetime import datetime
from nbformat import v4 as nbf
from copy import deepcopy
from flask import current_app
from flask_mongoengine import Document
from mongoengine import CASCADE, signals
from mongoengine.queryset import DoesNotExist
from mongoengine.fields import StringField, BooleanField, DictField
from mongoengine.fields import LazyReferenceField, ReferenceField
from mongoengine.fields import DateTimeField, ListField
from boltons.iterutils import remap
from decimal import Decimal

from mpcontribs.api import enter, valid_dict, Q_, max_dgts, quantity_keys, delimiter
from mpcontribs.api.notebooks import connect_kernel, execute

seed_nb = nbf.new_notebook()
seed_nb["cells"] = [nbf.new_code_cell("from mpcontribs.client import Client")]


def is_float(s):
    try:
        float(s)
    except ValueError:
        return False
    return True


def make_quantities(path, key, value):
    if key not in quantity_keys and isinstance(value, (str, int, float)):
        str_value = str(value)
        words = str_value.split()
        try_quantity = bool(len(words) == 2 and is_float(words[0]))

        if try_quantity or is_float(value):
            q = Q_(str_value).to_compact()

            if not q.check(0):
                q.ito_reduced_units()

            v = Decimal(str(q.magnitude))
            vt = v.as_tuple()

            if vt.exponent < 0:
                dgts = len(vt.digits)
                dgts = max_dgts if dgts > max_dgts else dgts
                v = f"{v:.{dgts}g}"

                if try_quantity:
                    q = Q_(f"{v} {q.units}")

            value = {"display": str(q), "value": q.magnitude, "unit": str(q.units)}

    return key, value


# TODO in flask-mongorest: also get all ReferenceFields when download requested
class Contributions(Document):
    project = LazyReferenceField(
        "Projects", required=True, passthrough=True, reverse_delete_rule=CASCADE
    )
    identifier = StringField(required=True, help_text="material/composition identifier")
    formula = StringField(help_text="formula (set dynamically)")
    is_public = BooleanField(
        required=True, default=False, help_text="public/private contribution"
    )
    data = DictField(
        default={}, validation=valid_dict, help_text="simple free-form data"
    )
    last_modified = DateTimeField(
        required=True, default=datetime.utcnow, help_text="time of last modification"
    )
    structures = ListField(ReferenceField("Structures"), default=[])
    tables = ListField(ReferenceField("Tables"), default=[])
    notebook = ReferenceField("Notebooks")
    meta = {
        "collection": "contributions",
        "indexes": [
            "project",
            "identifier",
            "formula",
            "is_public",
            "last_modified",
            {"fields": [(r"data.$**", 1)]},
        ],
    }

    @classmethod
    def pre_save_post_validation(cls, sender, document, **kwargs):
        from mpcontribs.api.projects.document import Column

        # set formula field
        if hasattr(document, "formula"):
            formulae = current_app.config["FORMULAE"]
            document.formula = formulae.get(document.identifier, document.identifier)

        # run data through Pint Quantities and save as dicts
        # TODO set maximum number of columns
        document.data = remap(document.data, visit=make_quantities, enter=enter)

        # project is LazyReferenceField
        project = document.project.fetch()

        # set columns field for project
        def update_columns(path, key, value):
            path = delimiter.join(["data"] + list(path) + [key])
            if isinstance(value, dict) and set(quantity_keys) == set(value.keys()):
                try:
                    column = project.columns.get(path=path)
                    q = Q_(value["display"])
                    if column.unit != value["unit"]:
                        # TODO catch dimensionality error
                        q.ito(column.unit)

                    # TODO min/max wrong if same contribution updated (add contribution RefField?)
                    val = q.magnitude
                    if val < column.min:
                        column.min = val
                    elif val > column.max:
                        column.max = val

                except DoesNotExist:
                    column = Column(path=path, unit=value["unit"])
                    column.min = column.max = value["value"]
                    project.columns.append(column)

            elif isinstance(value, str) and key not in quantity_keys:
                column = Column(path=path)
                project.columns.append(column)

            return True

        remap(document.data, visit=update_columns, enter=enter)

        # TODO catch if no structures/tables available anymore
        for path in ["structures", "tables"]:
            if getattr(document, path):
                try:
                    column = project.columns.get(path=path)
                except DoesNotExist:
                    column = Column(path=path)
                    project.columns.append(column)

        project.save()
        document.last_modified = datetime.utcnow()

        # generate notebook for this contribution
        from mpcontribs.api.notebooks.document import Notebooks

        cells = [
            nbf.new_code_cell(
                'client = Client(headers={"X-Consumer-Groups": "admin"})'
            ),
            nbf.new_markdown_cell("## Project"),
            nbf.new_code_cell(
                f'client.get_project("{document.project.name}").pretty()'
            ),
            nbf.new_markdown_cell("## Contribution"),
            nbf.new_code_cell(f'client.get_contribution("{document.id}").pretty()'),
        ]

        if document.tables:
            cells.append(nbf.new_markdown_cell("## Tables"))
            for table in document.tables:
                cells.append(
                    nbf.new_code_cell(f'client.get_table("{table.id}").plot()')
                )

        if document.structures:
            cells.append(nbf.new_markdown_cell("## Structures"))
            for structure in document.structures:
                cells.append(
                    nbf.new_code_cell(f'client.get_structure("{structure.id}")')
                )

        ws = connect_kernel()
        for cell in cells:
            if cell["cell_type"] == "code":
                cell["outputs"] = execute(ws, str(document.id), cell["source"])

        ws.close()
        cells[0] = nbf.new_code_cell("client = Client('<your-api-key-here>')")
        doc = deepcopy(seed_nb)
        doc["cells"] += cells
        nb = Notebooks(**doc)
        nb.save()
        if document.notebook is not None:
            document.notebook.delete()

        document.notebook = nb
        # TODO how to not trigger pre_save again?

    @classmethod
    def pre_delete(cls, sender, document, **kwargs):
        # TODO use post_delete?
        # TODO document.notebook.get().delete()?
        print(document.notebook)
        raise ValueError("stop")


signals.pre_save_post_validation.connect(
    Contributions.pre_save_post_validation, sender=Contributions
)
signals.pre_delete.connect(Contributions.pre_delete, sender=Contributions)
