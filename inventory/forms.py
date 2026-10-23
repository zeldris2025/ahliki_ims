import re
from django import forms
from .validators import (looks_like_container, normalise, validate_container_number,
                         validate_reference_number)
from .models import (Product, Supplier, Category, GoodsReceivedNote, GRNItem, Sale, SaleItem,
                     StockMovement, Pallet, ShelfLocation, Invoice, Container, ContainerItem,
                     ContainerComment, ContainerType, ShipmentTracking)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'supplier', 'unit_price', 'cost_price',
                  'reorder_level', 'unit', 'barcode', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'sku': forms.TextInput(attrs={'placeholder': 'e.g. ALW-RICE-25KG'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'phone', 'email', 'address']
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class GRNForm(forms.ModelForm):
    class Meta:
        model = GoodsReceivedNote
        fields = ['supplier', 'received_at', 'notes']
        widgets = {
            'received_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Container number, delivery notes, any remarks…'}),
        }


class GRNItemForm(forms.ModelForm):
    class Meta:
        model = GRNItem
        fields = ['product', 'quantity_received', 'expiry_date']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


GRNItemFormSet = forms.inlineformset_factory(
    GoodsReceivedNote, GRNItem,
    form=GRNItemForm, extra=3, can_delete=True
)


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['sale_number', 'customer_name', 'account_number', 'payment_method', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'unit_price']


SaleItemFormSet = forms.inlineformset_factory(
    Sale, SaleItem,
    form=SaleItemForm, extra=3, can_delete=True
)


class StockAdjustForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['product', 'movement_type', 'quantity', 'notes', 'batch_number', 'expiry_date']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


# ── WMS Forms ─────────────────────────────────────────────────────────────────

class PalletForm(forms.ModelForm):
    class Meta:
        model = Pallet
        fields = ['product', 'quantity', 'expiry_date', 'grn_item', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, grn=None, **kwargs):
        super().__init__(*args, **kwargs)
        if grn:
            self.fields['grn_item'].queryset = GRNItem.objects.filter(grn=grn)
            self.fields['grn_item'].required = False
        else:
            self.fields['grn_item'].queryset = GRNItem.objects.select_related('grn', 'product').order_by('-grn__received_at')
            self.fields['grn_item'].required = False


class CheckInForm(forms.Form):
    lot_number = forms.CharField(
        max_length=100,
        label='Pallet Lot Number',
        widget=forms.TextInput(attrs={'placeholder': 'Scan QR or type lot number', 'autocomplete': 'off'}),
    )
    shelf = forms.ModelChoiceField(
        queryset=ShelfLocation.objects.all(),
        label='Shelf Location',
        empty_label='— select shelf —',
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


class TransferForm(forms.Form):
    lot_number = forms.CharField(
        max_length=100,
        label='Pallet Lot Number',
        widget=forms.TextInput(attrs={'placeholder': 'Scan QR or type lot number', 'autocomplete': 'off'}),
    )
    to_shelf = forms.ModelChoiceField(
        queryset=ShelfLocation.objects.all(),
        label='Transfer To Shelf',
        empty_label='— select destination shelf —',
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


class ShelfAddForm(forms.Form):
    """Admin: add a new row of shelves, or extra levels to an existing row."""
    row = forms.RegexField(
        regex=r'^[A-Za-z]{1,10}$', max_length=10, label='Row',
        error_messages={'invalid': 'Use letters only, e.g. AA or COLD — the level number is added for you.'},
        widget=forms.TextInput(attrs={'placeholder': 'e.g. AA', 'autocomplete': 'off'}),
    )
    levels = forms.IntegerField(min_value=1, max_value=20, initial=3, label='Levels',
                                help_text='Creates levels 1 up to this number; existing ones are skipped.')

    def clean_row(self):
        return self.cleaned_data['row'].upper()


class ShelfEditForm(forms.Form):
    """Admin: move a shelf location to a different row / level (its code follows)."""
    row = ShelfAddForm.base_fields['row']
    level = forms.IntegerField(min_value=1, max_value=20, label='Level')

    def __init__(self, *args, shelf=None, **kwargs):
        self.shelf = shelf
        super().__init__(*args, **kwargs)

    def clean_row(self):
        return self.cleaned_data['row'].upper()

    def clean(self):
        data = super().clean()
        if 'row' in data and 'level' in data:
            data['code'] = f"{data['row']}{data['level']}"
            if ShelfLocation.objects.filter(code=data['code']).exclude(pk=self.shelf.pk).exists():
                raise forms.ValidationError(f"Shelf {data['code']} already exists.")
        return data


class PalletEditForm(forms.ModelForm):
    class Meta:
        model = Pallet
        fields = ['quantity', 'expiry_date', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional remarks…'}),
        }


class InvoiceUploadForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            'invoice_number', 'customer_name', 'account_number',
            'salesperson', 'payment_method', 'payment_terms',
            'sales_territory', 'due_date', 'total_amount', 'tax_amount',
            'notes', 'invoice_file',
        ]
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Any remarks…'}),
            'invoice_number': forms.TextInput(attrs={'placeholder': 'e.g. 72928'}),
            'customer_name': forms.TextInput(attrs={'placeholder': 'e.g. Taumeasina Resort'}),
            'account_number': forms.TextInput(attrs={'placeholder': 'e.g. TWN-001'}),
            'salesperson': forms.TextInput(attrs={'placeholder': 'e.g. Ropati'}),
            'payment_terms': forms.TextInput(attrs={'placeholder': 'e.g. Net 7 days'}),
            'sales_territory': forms.TextInput(attrs={'placeholder': 'e.g. TWN'}),
        }
        labels = {
            'invoice_file': 'Invoice PDF',
            'total_amount': 'Total (Incl. VAT)',
            'tax_amount': '15% VAT Amount',
        }


# ── Container Forms (Customs Broker + Warehouse) ─────────────────────────────

class ContainerForm(forms.ModelForm):
    class Meta:
        model = Container
        fields = ['tracking', 'container_number', 'container_type', 'vessel', 'arrival_date', 'supplier', 'notes']
        widgets = {
            'arrival_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Clearance remarks, seal number, anything worth noting…'}),
            'container_number': forms.TextInput(attrs={'placeholder': 'e.g. MSKU1234567', 'autocomplete': 'off'}),
            'vessel': forms.TextInput(attrs={'placeholder': 'e.g. Southern Moana V.24'}),
        }
        labels = {'arrival_date': 'Wharf arrival date', 'tracking': 'Tracked B/L (auto-fills details)'}

    def __init__(self, *args, cms_container=None, **kwargs):
        self.cms_container = cms_container
        super().__init__(*args, **kwargs)
        self.fields['tracking'].queryset = ShipmentTracking.objects.order_by('-created_at')
        self.fields['tracking'].empty_label = '— not from a tracked B/L —'
        # A supplier is needed so the GRN can be raised when the container is opened.
        self.fields['supplier'].required = True
        self.fields['supplier'].empty_label = '— select supplier —'
        # Only offer container types that are still in use; maintained in the admin panel.
        self.fields['container_type'].queryset = ContainerType.objects.filter(is_active=True)
        self.fields['container_type'].empty_label = '— select container type —'

    def clean_container_number(self):
        number = normalise(self.cleaned_data['container_number'])
        # Containers lodged before validation existed may be saved without a check digit;
        # only hold the broker to the standard when the number is new or being changed.
        # A list added for a CMS box keeps the code the yard already knows it by.
        if self.cms_container and number == normalise(self.cms_container.code):
            return number
        if number != (self.instance.container_number or '').upper():
            number = validate_container_number(number)
        return number


class ContainerItemForm(forms.ModelForm):
    class Meta:
        model = ContainerItem
        fields = ['product', 'quantity', 'expiry_date', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Optional'}),
        }
        labels = {'expiry_date': 'Expiry date (optional)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('name')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty < 1:
            raise forms.ValidationError('Quantity must be at least 1.')
        return qty


ContainerItemFormSet = forms.inlineformset_factory(
    Container, ContainerItem,
    form=ContainerItemForm, extra=3, can_delete=True
)


class ContainerCommentForm(forms.ModelForm):
    class Meta:
        model = ContainerComment
        fields = ['body', 'is_damage']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. 3 cartons crushed on the top layer — set aside for claim.'}),
        }
        labels = {'body': 'Comment', 'is_damage': 'Flag as damaged / broken goods'}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Comment cannot be empty.')
        return body


class ContainerPalletForm(forms.Form):
    """Build a pallet from a single container manifest line."""
    quantity = forms.IntegerField(min_value=1, label='Quantity on this pallet')
    expiry_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}),
                                  label='Expiry date (optional)')
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, container_item=None, **kwargs):
        self.container_item = container_item
        super().__init__(*args, **kwargs)
        if container_item is not None:
            remaining = container_item.remaining_quantity
            self.fields['quantity'].max_value = remaining
            self.fields['quantity'].widget.attrs.update({'max': remaining, 'min': 1})
            self.fields['quantity'].help_text = f'{remaining} of {container_item.quantity} still to palletize.'

    def clean_quantity(self):
        qty = self.cleaned_data['quantity']
        if self.container_item is not None and qty > self.container_item.remaining_quantity:
            raise forms.ValidationError(
                f'Only {self.container_item.remaining_quantity} left to palletize on this line.')
        return qty


# ── Shipment tracking (Customs Broker → Track Containers) ────────────────────

class ShipmentTrackingForm(forms.ModelForm):
    """Track a bill of lading with Terminal49. Only the B/L number is required;
    the voyage fields let the Atlas place the ship when Terminal49 cannot."""

    SCAC_CHOICES = [
        ('', 'Auto-detect shipping line'),
        ('MATS', 'Matson (MATS)'),
        ('CHNL', 'Swire Shipping / China Navigation (CHNL)'),
        ('ANNU', 'ANL (ANNU)'),
        ('CMDU', 'CMA CGM (CMDU)'),
        ('MAEU', 'Maersk (MAEU)'),
        ('SUDU', 'Hamburg Süd (SUDU)'),
        ('MSCU', 'MSC (MSCU)'),
        ('HLCU', 'Hapag-Lloyd (HLCU)'),
        ('PCIU', 'PIL — Pacific International Lines (PCIU)'),
        ('COSU', 'COSCO (COSU)'),
        ('ONEY', 'ONE (ONEY)'),
        ('EGLV', 'Evergreen (EGLV)'),
        ('ZIMU', 'ZIM (ZIMU)'),
    ]
    scac = forms.ChoiceField(choices=SCAC_CHOICES, required=False, label='Shipping line')

    class Meta:
        model = ShipmentTracking
        fields = ['request_number', 'request_type', 'scac', 'supplier', 'vessel_name', 'voyage_number',
                  'origin_port', 'departed_at', 'eta_at', 'container_numbers', 'show_in_my_containers']
        widgets = {
            'request_number': forms.TextInput(attrs={'placeholder': 'e.g. MATS1234567890', 'autocomplete': 'off',
                                                     'autofocus': True}),
            'vessel_name': forms.TextInput(attrs={'placeholder': 'e.g. Southern Moana'}),
            'voyage_number': forms.TextInput(attrs={'placeholder': 'e.g. 2441S'}),
            'origin_port': forms.TextInput(attrs={'placeholder': 'e.g. Auckland', 'list': 'portList',
                                                  'autocomplete': 'off'}),
            'departed_at': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'eta_at': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'container_numbers': forms.Textarea(attrs={'rows': 2, 'placeholder': 'MSKU1234567, MATU7654321'}),
        }
        labels = {'show_in_my_containers': 'Show in My Containers'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].empty_label = '— select supplier (optional) —'
        self.fields['departed_at'].help_text = 'Optional — estimated from the ETA if left blank'
        self.fields['eta_at'].help_text = 'Optional — Terminal49 fills this in where the plan allows'
        # Keep a stored SCAC selectable even if it is not one of the common lines above.
        current = (self.instance.scac or '').upper() if self.instance and self.instance.pk else ''
        if current and current not in dict(self.SCAC_CHOICES):
            self.fields['scac'].choices = self.SCAC_CHOICES + [(current, current)]

    def clean_request_number(self):
        number = normalise(self.cleaned_data['request_number'])
        clash = ShipmentTracking.objects.filter(request_number__iexact=number)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f'{number} is already being tracked.')
        return number

    def clean_container_numbers(self):
        numbers = [n for n in re.split(r'[\s,;]+', self.cleaned_data.get('container_numbers', '').upper()) if n]
        errors = []
        for n in numbers:
            try:
                validate_container_number(n)
            except forms.ValidationError as e:
                errors.extend(e.messages)
        if errors:
            raise forms.ValidationError(errors)
        return '\n'.join(dict.fromkeys(numbers))

    def clean(self):
        data = super().clean()
        number, kind = data.get('request_number'), data.get('request_type')
        if number and looks_like_container(number):
            # A container number is tracked as a container whatever was picked —
            # Terminal49 rejects it under any other type.
            kind = data['request_type'] = 'container'
            if number not in data.get('container_numbers', '').split('\n') and 'container_numbers' in data:
                data['container_numbers'] = '\n'.join(filter(None, [number, data['container_numbers']]))
        if number and kind:
            try:
                if kind == 'container':
                    validate_container_number(number)
                else:
                    validate_reference_number(number, dict(ShipmentTracking.TYPE_CHOICES)[kind])
            except forms.ValidationError as e:
                self.add_error('request_number', e)
        dep, eta = data.get('departed_at'), data.get('eta_at')
        if dep and eta and dep > eta:
            self.add_error('eta_at', 'ETA must be after the departure date.')
        return data


# ── CMS: Container Management (Customs Broker) ────────────────────────────────

from django.db.models import Q  # noqa: E402
from .models import CmsContainer, ShippingLine, Yard  # noqa: E402


def normalise_container_code(code):
    return re.sub(r'\s+', '', code or '').upper()


class CmsContainerForm(forms.ModelForm):
    class Meta:
        model = CmsContainer
        fields = ['code', 'description', 'yard', 'status', 'owner', 'vessel_voyage', 'arrival_date', 'driver', 'note']
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'e.g. SWLU1234567', 'autocomplete': 'off',
                                           'autofocus': True}),
            'description': forms.TextInput(attrs={'placeholder': "e.g. 40' reefer — frozen chicken"}),
            'vessel_voyage': forms.TextInput(attrs={'placeholder': 'e.g. Southern Lily 2441N'}),
            'arrival_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'driver': forms.TextInput(attrs={'placeholder': 'Who delivered it', 'list': 'driverList',
                                             'autocomplete': 'off'}),
            'note': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Seal number, damage, who to call…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        yards = Yard.objects.filter(is_active=True)
        if self.instance.pk and self.instance.yard_id:
            yards = Yard.objects.filter(Q(is_active=True) | Q(pk=self.instance.yard_id))
        self.fields['yard'].queryset = yards
        self.fields['yard'].empty_label = '— select yard —'
        self.fields['owner'].empty_label = '— select owner —'

    def clean_code(self):
        code = normalise_container_code(self.cleaned_data['code'])
        clash = CmsContainer.objects.filter(code=code, returned=False)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f'{code} is already in a yard. Return it before adding it again.')
        return code


class ShippingLineForm(forms.ModelForm):
    class Meta:
        model = ShippingLine
        fields = ['name', 'return_days']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. SWIRE'}),
            'return_days': forms.NumberInput(attrs={'placeholder': 'e.g. 14', 'min': 0}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip().upper()
        clash = ShippingLine.objects.filter(name__iexact=name)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f'{name} already exists.')
        return name


class ContainerReturnForm(forms.Form):
    returned_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    staff_name = forms.CharField(max_length=120)
    driver = forms.CharField(max_length=120, required=False)


class ContainerTransferForm(forms.Form):
    to_yard = forms.ModelChoiceField(queryset=Yard.objects.filter(is_active=True), label='Transfer to')
    transferred_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    driver = forms.CharField(max_length=120, required=False)
    staff_name = forms.CharField(max_length=120, required=False)
    note = forms.CharField(max_length=255, required=False)
