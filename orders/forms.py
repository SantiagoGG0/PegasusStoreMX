import re
import unicodedata

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from cart import mexico_geo

from .models import Order

# Los nombres "department" se conservan del proyecto de Colombia para que los
# arreglos se puedan portar sin pelear con nombres distintos; aquí son los
# estados de México (códigos ISO 3166-2: "AGU", "JAL", "CMX"...).
COLOMBIA_DEPARTMENTS = [("", "Selecciona tu estado")] + mexico_geo.states()
STATE_CHOICES = COLOMBIA_DEPARTMENTS

DEPARTMENT_NAME_TO_CODE = {name: code for code, name in COLOMBIA_DEPARTMENTS if code}

# Municipios con cobertura de contra entrega por estado (selector de ciudad).
CITIES_BY_DEPARTMENT_CODE: dict[str, list[str]] = mexico_geo.cities_by_state_code()


def _normalize_city(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii")
    return value.strip().lower()


def _city_key(value: str) -> str:
    """Como _normalize_city, pero además sin signos: "Gustavo A. Madero" → "gustavo a madero"."""
    key = re.sub(r"[^a-z0-9 ]+", " ", _normalize_city(value))
    return " ".join(key.split())


# normalized city name -> canonical spelling, scoped per department code. Se
# indexa también sin signos: "gustavo a madero" debe dar "Gustavo A. Madero".
_CITY_LOOKUP_BY_DEPARTMENT_CODE: dict[str, dict[str, str]] = {
    code: {
        **{_city_key(city): city for city in cities},
        **{_normalize_city(city): city for city in cities},
    }
    for code, cities in CITIES_BY_DEPARTMENT_CODE.items()
}

# normalized city name -> first department code that contains it (best-effort
# fallback for prefilling a state from a bare city name)
_DEPARTMENT_CODE_FOR_CITY_NORM: dict[str, str] = {}
for _code, _cities in CITIES_BY_DEPARTMENT_CODE.items():
    for _city in _cities:
        _DEPARTMENT_CODE_FOR_CITY_NORM.setdefault(_normalize_city(_city), _code)


# normalized city name -> every department code that has a city with that name
_DEPARTMENT_CODES_FOR_CITY_NORM: dict[str, list[str]] = {}
for _code, _cities in CITIES_BY_DEPARTMENT_CODE.items():
    for _city in _cities:
        for _key in {_normalize_city(_city), _city_key(_city)}:
            _DEPARTMENT_CODES_FOR_CITY_NORM.setdefault(_key, []).append(_code)

DEPARTMENT_LABEL_BY_CODE = {code: name for code, name in COLOMBIA_DEPARTMENTS if code}


def departments_for_city(city_name: str) -> list[str]:
    """Códigos de todos los departamentos que tienen una ciudad con ese nombre."""
    return (
        _DEPARTMENT_CODES_FOR_CITY_NORM.get(_normalize_city(city_name))
        or _DEPARTMENT_CODES_FOR_CITY_NORM.get(_city_key(city_name), [])
    )


def normalize_phone(raw: str) -> str:
    """"+52 1 55 1234-5678" → "5512345678": solo dígitos y sin la clave del
    país (52), ni el "1" ni el 044/045 que antes se marcaban para celulares."""
    digits = re.sub(r"\D", "", raw or "")
    for prefix in ("00521", "0052", "521", "52", "044", "045"):
        if digits.startswith(prefix) and len(digits) - len(prefix) == 10:
            return digits[len(prefix):]
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def normalize_zip(raw: str) -> str:
    """" 06 600 " → "06600"; un CP de 4 dígitos (se perdió el 0 inicial al
    copiarlo de una hoja de cálculo) se completa: "6600" → "06600"."""
    digits = re.sub(r"\D", "", raw or "")
    return digits.zfill(5) if len(digits) == 4 else digits


def state_code_for_department_name(name: str) -> str:
    if not name:
        return ""
    return DEPARTMENT_NAME_TO_CODE.get(name.strip(), "")


def department_code_for_city_name(city_name: str) -> str:
    """Best-effort department code for a bare city name (ambiguous cities
    resolve to whichever department happens to come first)."""
    if not city_name:
        return ""
    return _DEPARTMENT_CODE_FOR_CITY_NORM.get(_normalize_city(city_name), "")


def canonical_city_for_department(city_name: str, state_code: str) -> str:
    """Return the dataset's canonical spelling of city_name within
    state_code's municipality list, or "" if it doesn't belong there."""
    if not city_name or not state_code:
        return ""
    lookup = _CITY_LOOKUP_BY_DEPARTMENT_CODE.get(state_code, {})
    return lookup.get(_normalize_city(city_name)) or lookup.get(_city_key(city_name), "")


class CheckoutForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        label="Nombre",
        error_messages={"required": "Escribe tu nombre."},
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Tu nombre", "autocomplete": "given-name"}),
    )
    # No es obligatorio en el formulario: quien escribe "Juan Pérez" en Nombre
    # no debe ver un error; clean() lo separa.
    surname = forms.CharField(
        max_length=200,
        required=False,
        label="Apellido",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Tu apellido", "autocomplete": "family-name"}),
    )
    # Opcional: un correo mal escrito no bloquea la compra (ver clean_email).
    email = forms.CharField(
        max_length=320,
        label="Correo electrónico (opcional)",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "correo@ejemplo.com", "autocomplete": "email"}),
    )
    phone = forms.CharField(
        max_length=30,
        label="Teléfono / WhatsApp",
        error_messages={"required": "Escribe tu número de celular para que el repartidor te llame."},
        widget=forms.TextInput(attrs={
            "class": "form-input", "placeholder": "55 1234 5678", "type": "tel",
            "inputmode": "tel", "autocomplete": "tel-national",
        }),
    )
    address = forms.CharField(
        max_length=500,
        label="Calle y número",
        error_messages={"required": "Escribe la calle y el número."},
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Av. Juárez 123, int. 4", "autocomplete": "address-line1"}),
    )
    # Aparte, como en el formulario de Dropi México: la paquetería la necesita.
    colonia = forms.CharField(
        max_length=200,
        label="Colonia",
        error_messages={"required": "Escribe tu colonia."},
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Centro", "autocomplete": "address-line2"}),
    )
    state = forms.ChoiceField(
        choices=COLOMBIA_DEPARTMENTS,
        label="Estado",
        widget=forms.Select(attrs={"class": "form-input"}),
        error_messages={"required": "Selecciona tu estado."},
    )
    city = forms.CharField(
        max_length=200,
        label="Municipio o alcaldía",
        widget=forms.HiddenInput(),
        error_messages={"required": "Selecciona tu municipio o alcaldía."},
    )
    # Obligatorio: en México la paquetería enruta por CP.
    zip_code = forms.CharField(
        max_length=10,
        label="Código postal",
        error_messages={"required": "Escribe tu código postal (5 dígitos)."},
        widget=forms.TextInput(attrs={
            "class": "form-input", "placeholder": "06600", "inputmode": "numeric",
            "autocomplete": "postal-code",
        }),
    )
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_CHOICES,
        label="Método de pago",
        widget=forms.RadioSelect,
    )
    notes = forms.CharField(
        required=False,
        max_length=1000,
        label="Indicaciones para el repartidor (opcional)",
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 2, "placeholder": "Torre 3, apto 502 · casa de rejas verdes · frente a la tienda…"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(settings, "ENABLE_PREPAID_PAYMENT", False):
            self.fields["payment_method"].choices = [
                (Order.PAYMENT_COD, "Pago contra entrega"),
            ]
            self.fields["payment_method"].initial = Order.PAYMENT_COD
            # A single-choice radio has nothing to choose — it was rendering
            # as a bare, unstyled native radio button + label sitting right
            # above the styled COD confirmation box in the template (same
            # "Pago contra entrega" text shown twice, once ugly once pretty).
            # A hidden input still posts the fixed value correctly without
            # showing a choice that isn't one.
            self.fields["payment_method"].widget = forms.HiddenInput()

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone", ""))
        if len(phone) == 10:
            return phone
        if not phone:
            raise ValidationError("Escribe tu número de celular, por ejemplo 55 1234 5678.")
        raise ValidationError(
            f"El número tiene {len(phone)} dígitos y un celular en México tiene 10 "
            "(por ejemplo 55 1234 5678). Revísalo."
        )

    def clean_colonia(self):
        # "Col. Centro" / "colonia centro" → "Centro" (el prefijo lo pone full_address).
        value = " ".join((self.cleaned_data.get("colonia") or "").split())
        return re.sub(r"^(col(onia)?\.?)\s+", "", value, flags=re.IGNORECASE)

    def clean_zip_code(self):
        zip_code = normalize_zip(self.cleaned_data.get("zip_code", ""))
        if len(zip_code) != 5:
            raise ValidationError("El código postal tiene 5 dígitos, por ejemplo 06600.")
        return zip_code

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").replace(" ", "").strip(".,;")
        if not email:
            return ""
        try:
            validate_email(email)
        except ValidationError:
            # Es opcional y la confirmación llega por WhatsApp: mejor perder el
            # correo que la venta.
            return ""
        return email.lower()

    def clean(self):
        cleaned = super().clean()
        name = " ".join((cleaned.get("name") or "").split())
        surname = " ".join((cleaned.get("surname") or "").split())
        if name and not surname:
            # "Juan Pérez" → Juan / Pérez; "Ana María López Gómez" → Ana María / López Gómez.
            parts = name.split(" ")
            if len(parts) >= 2:
                cut = 2 if len(parts) >= 4 else len(parts) - 1
                name, surname = " ".join(parts[:cut]), " ".join(parts[cut:])
            else:
                self.add_error("surname", "Escribe tu apellido.")
        cleaned["name"], cleaned["surname"] = name, surname

        state_code = cleaned.get("state")
        city = (cleaned.get("city") or "").strip()
        # Sin estado/municipio válidos pero con un CP conocido de una sola
        # ciudad: se completan desde el CP en vez de rechazar el pedido.
        zip_matches = mexico_geo.lookup_zip(cleaned.get("zip_code", ""))
        city_ok = bool(city) and bool(canonical_city_for_department(city, state_code) or departments_for_city(city))
        if len(zip_matches) == 1 and not city_ok:
            state_code, city = zip_matches[0]
            cleaned["state"], cleaned["city"] = state_code, city
            self.errors.pop("state", None)
            self.errors.pop("city", None)
        if state_code and city:
            canonical = canonical_city_for_department(city, state_code)
            if canonical:
                cleaned["city"] = canonical
                return cleaned
            # Ciudad de otro departamento (p. ej. Bogotá con Cundinamarca): si
            # existe en uno solo, se corrige el departamento en vez de rechazar
            # el pedido; si existe en varios, se pide elegir cuál.
            others = departments_for_city(city)
            if len(others) == 1:
                cleaned["state"] = others[0]
                cleaned["city"] = canonical_city_for_department(city, others[0])
            elif others:
                names = " o ".join(DEPARTMENT_LABEL_BY_CODE[c] for c in others)
                self.add_error("state", f"Hay un municipio llamado {city} en {names}. Elige el estado correcto.")
            else:
                self.add_error(
                    "city",
                    f"No tenemos entrega con pago contra entrega en «{city}» "
                    f"({DEPARTMENT_LABEL_BY_CODE.get(state_code, 'ese estado')}). "
                    "Escribe las primeras letras y elige tu municipio de la lista.",
                )
        return cleaned
