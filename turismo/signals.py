from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from .models import PerfilUsuario


@receiver(user_signed_up)
def crear_perfil_usuario_social(request, user, **kwargs):
    PerfilUsuario.objects.get_or_create(usuario=user)