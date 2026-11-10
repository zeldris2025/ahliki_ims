from django import forms

from .models import Enquiry


class EnquiryForm(forms.ModelForm):
    # Hidden from people; bots that fill every field get caught by it.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'tabindex': '-1', 'autocomplete': 'off'}))

    class Meta:
        model = Enquiry
        fields = ['name', 'email', 'phone', 'topic', 'level', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your full name', 'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Optional', 'autocomplete': 'tel'}),
            'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'How can we help?'}),
        }

    def is_spam(self):
        return bool(self.cleaned_data.get('website'))
