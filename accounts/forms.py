from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class PostCheckoutSignupForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-input", "readonly": "readonly"}),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "password1", "password2")

    def __init__(self, *args, order_email=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_email = (order_email or "").strip().lower()
        if self.order_email:
            self.fields["email"].initial = self.order_email
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update({"class": "form-input"})

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if self.order_email and email != self.order_email:
            raise forms.ValidationError(
                "El correo debe coincidir con el de tu pedido."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta con este correo. Inicia sesión para vincular tu pedido."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class VoluntarySignupForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-input", "autocomplete": "email"}),
    )

    class Meta:
        model = User
        fields = ("first_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update({"class": "form-input"})

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta con este correo. "
                '<a href="/cuenta/entrar/" class="text-gold underline">Inicia sesión</a>.'
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        if commit:
            user.save()
        return user


class StoreLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-input", "autocomplete": "email"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "autocomplete": "current-password"}),
    )


class AvatarUploadForm(forms.Form):
    avatar = forms.ImageField(
        label="Foto de perfil",
        widget=forms.FileInput(attrs={"accept": "image/*", "class": "sr-only", "id": "avatar-input"}),
    )
