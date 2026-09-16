from django import template

register = template.Library()


@register.filter
def get_field(form, name):
    """Acessa um campo de um form pelo nome vindo de uma variável (não literal) — form|get_field:nome."""
    return form[name]


@register.filter
def get_attr(obj, name):
    """Acessa um atributo/valor de instância pelo nome vindo de uma variável — obj|get_attr:nome."""
    return getattr(obj, name, "")


@register.filter
def get_verbose_name(instance, name):
    """Rótulo humano (verbose_name) de um campo do model, pelo nome vindo de uma variável."""
    return instance._meta.get_field(name).verbose_name
