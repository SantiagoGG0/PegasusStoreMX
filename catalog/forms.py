from django import forms

from catalog.models import ProductReview


class ProductReviewForm(forms.ModelForm):
    score = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect(attrs={"class": "review-score-input"}),
        label="Puntuación",
    )
    comment = forms.CharField(
        required=False,
        label="Comentario (opcional)",
        widget=forms.Textarea(
            attrs={
                "class": "form-input w-full min-h-[88px] resize-y",
                "rows": 3,
                "placeholder": "Cuéntanos qué te pareció el producto…",
                "maxlength": "2000",
            }
        ),
    )

    class Meta:
        model = ProductReview
        fields = ("score", "comment")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["score"].initial = self.instance.score
            self.fields["comment"].initial = self.instance.comment
