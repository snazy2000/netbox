import re

from mptt.forms import TreeNodeChoiceField

from django import forms
from django.contrib.postgres.forms.array import SimpleArrayField
from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from extras.forms import CustomFieldForm, CustomFieldBulkEditForm, CustomFieldFilterForm
from ipam.models import IPAddress
from tenancy.models import Tenant
from utilities.forms import (
    APISelect, add_blank_choice, ArrayFieldSelectMultiple, BootstrapMixin, BulkEditForm, BulkImportForm, CommentField,
    CSVDataField, ExpandableNameField, FilterChoiceField, FlexibleModelChoiceField, Livesearch, SelectWithDisabled,
    SmallTextarea, SlugField, FilterTreeNodeMultipleChoiceField,
)

from .formfields import MACAddressFormField
from .models import (
    DeviceBay, DeviceBayTemplate, CONNECTION_STATUS_CHOICES, CONNECTION_STATUS_PLANNED, CONNECTION_STATUS_CONNECTED,
    ConsolePort, ConsolePortTemplate, ConsoleServerPort, ConsoleServerPortTemplate, Device, DeviceRole, DeviceType,
    Interface, IFACE_FF_CHOICES, IFACE_FF_LAG, IFACE_ORDERING_CHOICES, InterfaceConnection, InterfaceTemplate,
    Manufacturer, Module, Platform, PowerOutlet, PowerOutletTemplate, PowerPort, PowerPortTemplate, RACK_TYPE_CHOICES,
    RACK_WIDTH_CHOICES, Rack, RackGroup, RackReservation, RackRole, Region, Site, STATUS_CHOICES, SUBDEVICE_ROLE_CHILD,
    SUBDEVICE_ROLE_PARENT, VIRTUAL_IFACE_TYPES
)


FORM_STATUS_CHOICES = [
    ['', '---------'],
]

FORM_STATUS_CHOICES += STATUS_CHOICES

DEVICE_BY_PK_RE = '{\d+\}'


def get_device_by_name_or_pk(name):
    """
    Attempt to retrieve a device by either its name or primary key ('{pk}').
    """
    if re.match(DEVICE_BY_PK_RE, name):
        pk = name.strip('{}')
        device = Device.objects.get(pk=pk)
    else:
        device = Device.objects.get(name=name)
    return device


def validate_connection_status(value):
    """
    Custom validator for connection statuses. value must be either "planned" or "connected" (case-insensitive).
    """
    if value.lower() not in ['planned', 'connected']:
        raise ValidationError('Invalid connection status ({}); must be either "planned" or "connected".'.format(value))


class DeviceComponentForm(BootstrapMixin, forms.Form):
    """
    Allow inclusion of the parent device as context for limiting field choices.
    """
    def __init__(self, device, *args, **kwargs):
        self.device = device
        super(DeviceComponentForm, self).__init__(*args, **kwargs)


#
# Regions
#

class RegionForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = Region
        fields = ['parent', 'name', 'slug']


#
# Sites
#

class SiteForm(BootstrapMixin, CustomFieldForm):
    region = TreeNodeChoiceField(queryset=Region.objects.all(), required=False)
    slug = SlugField()
    comments = CommentField()

    class Meta:
        model = Site
        fields = [
            'name', 'slug', 'region', 'tenant', 'facility', 'asn', 'physical_address', 'shipping_address',
            'contact_name', 'contact_phone', 'contact_email', 'comments',
        ]
        widgets = {
            'physical_address': SmallTextarea(attrs={'rows': 3}),
            'shipping_address': SmallTextarea(attrs={'rows': 3}),
        }
        help_texts = {
            'name': "Full name of the site",
            'facility': "Data center provider and facility (e.g. Equinix NY7)",
            'asn': "BGP autonomous system number",
            'physical_address': "Physical location of the building (e.g. for GPS)",
            'shipping_address': "If different from the physical address"
        }


class SiteFromCSVForm(forms.ModelForm):
    region = forms.ModelChoiceField(
        Region.objects.all(), to_field_name='name', required=False, error_messages={
            'invalid_choice': 'Tenant not found.'
        }
    )
    tenant = forms.ModelChoiceField(
        Tenant.objects.all(), to_field_name='name', required=False, error_messages={
            'invalid_choice': 'Tenant not found.'
        }
    )

    class Meta:
        model = Site
        fields = [
            'name', 'slug', 'region', 'tenant', 'facility', 'asn', 'contact_name', 'contact_phone', 'contact_email',
        ]


class SiteImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=SiteFromCSVForm)


class SiteBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=Site.objects.all(), widget=forms.MultipleHiddenInput)
    region = TreeNodeChoiceField(queryset=Region.objects.all(), required=False)
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    asn = forms.IntegerField(min_value=1, max_value=4294967295, required=False, label='ASN')

    class Meta:
        nullable_fields = ['region', 'tenant', 'asn']


class SiteFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = Site
    q = forms.CharField(required=False, label='Search')
    region = FilterTreeNodeMultipleChoiceField(
        queryset=Region.objects.annotate(filter_count=Count('sites')),
        to_field_name='slug',
        required=False,
    )
    tenant = FilterChoiceField(
        queryset=Tenant.objects.annotate(filter_count=Count('sites')),
        to_field_name='slug',
        null_option=(0, 'None')
    )


#
# Rack groups
#

class RackGroupForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = RackGroup
        fields = ['site', 'name', 'slug']


class RackGroupFilterForm(BootstrapMixin, forms.Form):
    site = FilterChoiceField(queryset=Site.objects.annotate(filter_count=Count('rack_groups')), to_field_name='slug')


#
# Rack roles
#

class RackRoleForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = RackRole
        fields = ['name', 'slug', 'color']


#
# Racks
#

class RackForm(BootstrapMixin, CustomFieldForm):
    group = forms.ModelChoiceField(queryset=RackGroup.objects.all(), required=False, label='Group', widget=APISelect(
        api_url='/api/dcim/rack-groups/?site_id={{site}}',
    ))
    comments = CommentField()

    class Meta:
        model = Rack
        fields = ['site', 'group', 'name', 'facility_id', 'tenant', 'role', 'type', 'width', 'u_height', 'desc_units',
                  'comments']
        help_texts = {
            'site': "The site at which the rack exists",
            'name': "Organizational rack name",
            'facility_id': "The unique rack ID assigned by the facility",
            'u_height': "Height in rack units",
        }
        widgets = {
            'site': forms.Select(attrs={'filter-for': 'group'}),
        }

    def __init__(self, *args, **kwargs):

        super(RackForm, self).__init__(*args, **kwargs)

        # Limit rack group choices
        if self.is_bound and self.data.get('site'):
            self.fields['group'].queryset = RackGroup.objects.filter(site__pk=self.data['site'])
        elif self.initial.get('site'):
            self.fields['group'].queryset = RackGroup.objects.filter(site=self.initial['site'])
        else:
            self.fields['group'].choices = []


class RackFromCSVForm(forms.ModelForm):
    site = forms.ModelChoiceField(queryset=Site.objects.all(), to_field_name='name',
                                  error_messages={'invalid_choice': 'Site not found.'})
    group_name = forms.CharField(required=False)
    tenant = forms.ModelChoiceField(Tenant.objects.all(), to_field_name='name', required=False,
                                    error_messages={'invalid_choice': 'Tenant not found.'})
    role = forms.ModelChoiceField(RackRole.objects.all(), to_field_name='name', required=False,
                                  error_messages={'invalid_choice': 'Role not found.'})
    type = forms.CharField(required=False)

    class Meta:
        model = Rack
        fields = ['site', 'group_name', 'name', 'facility_id', 'tenant', 'role', 'type', 'width', 'u_height',
                  'desc_units']

    def clean(self):

        site = self.cleaned_data.get('site')
        group = self.cleaned_data.get('group_name')

        # Validate rack group
        if site and group:
            try:
                self.instance.group = RackGroup.objects.get(site=site, name=group)
            except RackGroup.DoesNotExist:
                self.add_error('group_name', "Invalid rack group ({})".format(group))

    def clean_type(self):
        rack_type = self.cleaned_data['type']
        if not rack_type:
            return None
        try:
            choices = {v.lower(): k for k, v in RACK_TYPE_CHOICES}
            return choices[rack_type.lower()]
        except KeyError:
            raise forms.ValidationError('Invalid rack type ({}). Valid choices are: {}.'.format(
                rack_type,
                ', '.join({v: k for k, v in RACK_TYPE_CHOICES}),
            ))


class RackImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=RackFromCSVForm)


class RackBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=Rack.objects.all(), widget=forms.MultipleHiddenInput)
    site = forms.ModelChoiceField(queryset=Site.objects.all(), required=False, label='Site')
    group = forms.ModelChoiceField(queryset=RackGroup.objects.all(), required=False, label='Group')
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    role = forms.ModelChoiceField(queryset=RackRole.objects.all(), required=False)
    type = forms.ChoiceField(choices=add_blank_choice(RACK_TYPE_CHOICES), required=False, label='Type')
    width = forms.ChoiceField(choices=add_blank_choice(RACK_WIDTH_CHOICES), required=False, label='Width')
    u_height = forms.IntegerField(required=False, label='Height (U)')
    comments = CommentField(widget=SmallTextarea)

    class Meta:
        nullable_fields = ['group', 'tenant', 'role', 'comments']


class RackFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = Rack
    q = forms.CharField(required=False, label='Search')
    site = FilterChoiceField(
        queryset=Site.objects.annotate(filter_count=Count('racks')),
        to_field_name='slug'
    )
    group_id = FilterChoiceField(
        queryset=RackGroup.objects.select_related('site').annotate(filter_count=Count('racks')),
        label='Rack group',
        null_option=(0, 'None')
    )
    tenant = FilterChoiceField(
        queryset=Tenant.objects.annotate(filter_count=Count('racks')),
        to_field_name='slug',
        null_option=(0, 'None')
    )
    role = FilterChoiceField(
        queryset=RackRole.objects.annotate(filter_count=Count('racks')),
        to_field_name='slug',
        null_option=(0, 'None')
    )


#
# Rack reservations
#

class RackReservationForm(BootstrapMixin, forms.ModelForm):
    units = SimpleArrayField(forms.IntegerField(), widget=ArrayFieldSelectMultiple(attrs={'size': 10}))

    class Meta:
        model = RackReservation
        fields = ['units', 'description']

    def __init__(self, *args, **kwargs):

        super(RackReservationForm, self).__init__(*args, **kwargs)

        # Populate rack unit choices
        self.fields['units'].widget.choices = self._get_unit_choices()

    def _get_unit_choices(self):
        rack = self.instance.rack
        reserved_units = []
        for resv in rack.reservations.exclude(pk=self.instance.pk):
            for u in resv.units:
                reserved_units.append(u)
        unit_choices = [(u, {'label': str(u), 'disabled': u in reserved_units}) for u in rack.units]
        return unit_choices


class RackReservationFilterForm(BootstrapMixin, forms.Form):
    q = forms.CharField(required=False, label='Search')
    site = FilterChoiceField(
        queryset=Site.objects.annotate(filter_count=Count('racks__reservations')),
        to_field_name='slug'
    )
    group_id = FilterChoiceField(
        queryset=RackGroup.objects.select_related('site').annotate(filter_count=Count('racks__reservations')),
        label='Rack group',
        null_option=(0, 'None')
    )


#
# Manufacturers
#

class ManufacturerForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = Manufacturer
        fields = ['name', 'slug']


#
# Device types
#

class DeviceTypeForm(BootstrapMixin, CustomFieldForm):
    slug = SlugField(slug_source='model')

    class Meta:
        model = DeviceType
        fields = ['manufacturer', 'model', 'slug', 'part_number', 'u_height', 'is_full_depth', 'is_console_server',
                  'is_pdu', 'is_network_device', 'subdevice_role', 'interface_ordering', 'comments']
        labels = {
            'interface_ordering': 'Order interfaces by',
        }


class DeviceTypeBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=DeviceType.objects.all(), widget=forms.MultipleHiddenInput)
    manufacturer = forms.ModelChoiceField(queryset=Manufacturer.objects.all(), required=False)
    u_height = forms.IntegerField(min_value=1, required=False)
    interface_ordering = forms.ChoiceField(choices=add_blank_choice(IFACE_ORDERING_CHOICES), required=False)

    class Meta:
        nullable_fields = []


class DeviceTypeFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = DeviceType
    q = forms.CharField(required=False, label='Search')
    manufacturer = FilterChoiceField(
        queryset=Manufacturer.objects.annotate(filter_count=Count('device_types')),
        to_field_name='slug'
    )
    is_console_server = forms.BooleanField(
        required=False, label='Is a console server', widget=forms.CheckboxInput(attrs={'value': 'True'}))
    is_pdu = forms.BooleanField(
        required=False, label='Is a PDU', widget=forms.CheckboxInput(attrs={'value': 'True'})
    )
    is_network_device = forms.BooleanField(
        required=False, label='Is a network device', widget=forms.CheckboxInput(attrs={'value': 'True'})
    )
    subdevice_role = forms.NullBooleanField(
        required=False, label='Subdevice role', widget=forms.Select(choices=(
            ('', '---------'),
            (SUBDEVICE_ROLE_PARENT, 'Parent'),
            (SUBDEVICE_ROLE_CHILD, 'Child'),
        ))
    )


#
# Device component templates
#

class ConsolePortTemplateForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = ConsolePortTemplate
        fields = ['device_type', 'name']
        widgets = {
            'device_type': forms.HiddenInput(),
        }


class ConsolePortTemplateCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class ConsoleServerPortTemplateForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = ConsoleServerPortTemplate
        fields = ['device_type', 'name']
        widgets = {
            'device_type': forms.HiddenInput(),
        }


class ConsoleServerPortTemplateCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class PowerPortTemplateForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = PowerPortTemplate
        fields = ['device_type', 'name']
        widgets = {
            'device_type': forms.HiddenInput(),
        }


class PowerPortTemplateCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class PowerOutletTemplateForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = PowerOutletTemplate
        fields = ['device_type', 'name']
        widgets = {
            'device_type': forms.HiddenInput(),
        }


class PowerOutletTemplateCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class InterfaceTemplateForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = InterfaceTemplate
        fields = ['device_type', 'name', 'form_factor', 'mgmt_only']
        widgets = {
            'device_type': forms.HiddenInput(),
        }


class InterfaceTemplateCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')
    form_factor = forms.ChoiceField(choices=IFACE_FF_CHOICES)
    mgmt_only = forms.BooleanField(required=False, label='OOB Management')


class InterfaceTemplateBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=InterfaceTemplate.objects.all(), widget=forms.MultipleHiddenInput)
    form_factor = forms.ChoiceField(choices=add_blank_choice(IFACE_FF_CHOICES), required=False)

    class Meta:
        nullable_fields = []


class DeviceBayTemplateForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = DeviceBayTemplate
        fields = ['device_type', 'name']
        widgets = {
            'device_type': forms.HiddenInput(),
        }


class DeviceBayTemplateCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


#
# Device roles
#

class DeviceRoleForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = DeviceRole
        fields = ['name', 'slug', 'color']


#
# Platforms
#

class PlatformForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = Platform
        fields = ['name', 'slug']


#
# Devices
#

class DeviceForm(BootstrapMixin, CustomFieldForm):
    site = forms.ModelChoiceField(queryset=Site.objects.all(), widget=forms.Select(attrs={'filter-for': 'rack'}))
    rack = forms.ModelChoiceField(queryset=Rack.objects.all(), required=False, widget=APISelect(
        api_url='/api/dcim/racks/?site_id={{site}}',
        display_field='display_name',
        attrs={'filter-for': 'position'}
    ))
    position = forms.TypedChoiceField(required=False, empty_value=None,
                                      help_text="The lowest-numbered unit occupied by the device",
                                      widget=APISelect(api_url='/api/dcim/racks/{{rack}}/rack-units/?face={{face}}',
                                                       disabled_indicator='device'))
    manufacturer = forms.ModelChoiceField(queryset=Manufacturer.objects.all(),
                                          widget=forms.Select(attrs={'filter-for': 'device_type'}))
    device_type = forms.ModelChoiceField(queryset=DeviceType.objects.all(), label='Device type', widget=APISelect(
        api_url='/api/dcim/device-types/?manufacturer_id={{manufacturer}}',
        display_field='model'
    ))
    comments = CommentField()

    class Meta:
        model = Device
        fields = ['name', 'device_role', 'tenant', 'device_type', 'serial', 'asset_tag', 'site', 'rack', 'position',
                  'face', 'status', 'platform', 'primary_ip4', 'primary_ip6', 'comments']
        help_texts = {
            'device_role': "The function this device serves",
            'serial': "Chassis serial number",
        }
        widgets = {
            'face': forms.Select(attrs={'filter-for': 'position'}),
            'manufacturer': forms.Select(attrs={'filter-for': 'device_type'}),
        }

    def __init__(self, *args, **kwargs):

        super(DeviceForm, self).__init__(*args, **kwargs)

        if self.instance.pk:

            # Initialize helper selections
            self.initial['site'] = self.instance.site
            self.initial['manufacturer'] = self.instance.device_type.manufacturer

            # Compile list of choices for primary IPv4 and IPv6 addresses
            for family in [4, 6]:
                ip_choices = []
                interface_ips = IPAddress.objects.filter(family=family, interface__device=self.instance)
                ip_choices += [(ip.id, u'{} ({})'.format(ip.address, ip.interface)) for ip in interface_ips]
                nat_ips = IPAddress.objects.filter(family=family, nat_inside__interface__device=self.instance)\
                    .select_related('nat_inside__interface')
                ip_choices += [(ip.id, u'{} ({} NAT)'.format(ip.address, ip.nat_inside.interface)) for ip in nat_ips]
                self.fields['primary_ip{}'.format(family)].choices = [(None, '---------')] + ip_choices

            # If editing an existing device, exclude it from the list of occupied rack units. This ensures that a device
            # can be flipped from one face to another.
            self.fields['position'].widget.attrs['api-url'] += '&exclude={}'.format(self.instance.pk)

        else:

            # An object that doesn't exist yet can't have any IPs assigned to it
            self.fields['primary_ip4'].choices = []
            self.fields['primary_ip4'].widget.attrs['readonly'] = True
            self.fields['primary_ip6'].choices = []
            self.fields['primary_ip6'].widget.attrs['readonly'] = True

        # Limit rack choices
        if self.is_bound and self.data.get('site'):
            self.fields['rack'].queryset = Rack.objects.filter(site__pk=self.data['site'])
        elif self.initial.get('site'):
            self.fields['rack'].queryset = Rack.objects.filter(site=self.initial['site'])
        else:
            self.fields['rack'].choices = []

        # Rack position
        pk = self.instance.pk if self.instance.pk else None
        try:
            if self.is_bound and self.data.get('rack') and str(self.data.get('face')):
                position_choices = Rack.objects.get(pk=self.data['rack'])\
                    .get_rack_units(face=self.data.get('face'), exclude=pk)
            elif self.initial.get('rack') and str(self.initial.get('face')):
                position_choices = Rack.objects.get(pk=self.initial['rack'])\
                    .get_rack_units(face=self.initial.get('face'), exclude=pk)
            else:
                position_choices = []
        except Rack.DoesNotExist:
            position_choices = []
        self.fields['position'].choices = [('', '---------')] + [
            (p['id'], {
                'label': p['name'],
                'disabled': bool(p['device'] and p['id'] != self.initial.get('position')),
            }) for p in position_choices
        ]

        # Limit device_type choices
        if self.is_bound:
            self.fields['device_type'].queryset = DeviceType.objects.filter(manufacturer__pk=self.data['manufacturer'])\
                .select_related('manufacturer')
        elif self.initial.get('manufacturer'):
            self.fields['device_type'].queryset = DeviceType.objects.filter(manufacturer=self.initial['manufacturer'])\
                .select_related('manufacturer')
        else:
            self.fields['device_type'].choices = []

        # Disable rack assignment if this is a child device installed in a parent device
        if pk and self.instance.device_type.is_child_device and hasattr(self.instance, 'parent_bay'):
            self.fields['site'].disabled = True
            self.fields['rack'].disabled = True
            self.initial['site'] = self.instance.parent_bay.device.site_id
            self.initial['rack'] = self.instance.parent_bay.device.rack_id


class BaseDeviceFromCSVForm(forms.ModelForm):
    device_role = forms.ModelChoiceField(queryset=DeviceRole.objects.all(), to_field_name='name',
                                         error_messages={'invalid_choice': 'Invalid device role.'})
    tenant = forms.ModelChoiceField(Tenant.objects.all(), to_field_name='name', required=False,
                                    error_messages={'invalid_choice': 'Tenant not found.'})
    manufacturer = forms.ModelChoiceField(queryset=Manufacturer.objects.all(), to_field_name='name',
                                          error_messages={'invalid_choice': 'Invalid manufacturer.'})
    model_name = forms.CharField()
    platform = forms.ModelChoiceField(queryset=Platform.objects.all(), required=False, to_field_name='name',
                                      error_messages={'invalid_choice': 'Invalid platform.'})

    class Meta:
        fields = []
        model = Device

    def clean(self):

        manufacturer = self.cleaned_data.get('manufacturer')
        model_name = self.cleaned_data.get('model_name')

        # Validate device type
        if manufacturer and model_name:
            try:
                self.instance.device_type = DeviceType.objects.get(manufacturer=manufacturer, model=model_name)
            except DeviceType.DoesNotExist:
                self.add_error('model_name', "Invalid device type ({} {})".format(manufacturer, model_name))


class DeviceFromCSVForm(BaseDeviceFromCSVForm):
    site = forms.ModelChoiceField(queryset=Site.objects.all(), to_field_name='name', error_messages={
        'invalid_choice': 'Invalid site name.',
    })
    rack_name = forms.CharField(required=False)
    face = forms.CharField(required=False)

    class Meta(BaseDeviceFromCSVForm.Meta):
        fields = ['name', 'device_role', 'tenant', 'manufacturer', 'model_name', 'platform', 'serial', 'asset_tag',
                  'site', 'rack_name', 'position', 'face']

    def clean(self):

        super(DeviceFromCSVForm, self).clean()

        site = self.cleaned_data.get('site')
        rack_name = self.cleaned_data.get('rack_name')

        # Validate rack
        if site and rack_name:
            try:
                self.instance.rack = Rack.objects.get(site=site, name=rack_name)
            except Rack.DoesNotExist:
                self.add_error('rack_name', "Invalid rack ({})".format(rack_name))

    def clean_face(self):
        face = self.cleaned_data['face']
        if not face:
            return None
        try:
            return {
                'front': 0,
                'rear': 1,
            }[face.lower()]
        except KeyError:
            raise forms.ValidationError('Invalid rack face ({}); must be "front" or "rear".'.format(face))


class ChildDeviceFromCSVForm(BaseDeviceFromCSVForm):
    parent = FlexibleModelChoiceField(
        queryset=Device.objects.all(),
        to_field_name='name',
        required=False,
        error_messages={
            'invalid_choice': 'Parent device not found.'
        }
    )
    device_bay_name = forms.CharField(required=False)

    class Meta(BaseDeviceFromCSVForm.Meta):
        fields = [
            'name', 'device_role', 'tenant', 'manufacturer', 'model_name', 'platform', 'serial', 'asset_tag', 'parent',
            'device_bay_name',
        ]

    def clean(self):

        super(ChildDeviceFromCSVForm, self).clean()

        parent = self.cleaned_data.get('parent')
        device_bay_name = self.cleaned_data.get('device_bay_name')

        # Validate device bay
        if parent and device_bay_name:
            try:
                device_bay = DeviceBay.objects.get(device=parent, name=device_bay_name)
                if device_bay.installed_device:
                    self.add_error('device_bay_name',
                                   "Device bay ({} {}) is already occupied".format(parent, device_bay_name))
                else:
                    self.instance.parent_bay = device_bay
            except DeviceBay.DoesNotExist:
                self.add_error('device_bay_name', "Parent device/bay ({} {}) not found".format(parent, device_bay_name))


class DeviceImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=DeviceFromCSVForm)


class ChildDeviceImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=ChildDeviceFromCSVForm)


class DeviceBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=Device.objects.all(), widget=forms.MultipleHiddenInput)
    device_type = forms.ModelChoiceField(queryset=DeviceType.objects.all(), required=False, label='Type')
    device_role = forms.ModelChoiceField(queryset=DeviceRole.objects.all(), required=False, label='Role')
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    platform = forms.ModelChoiceField(queryset=Platform.objects.all(), required=False)
    status = forms.ChoiceField(choices=FORM_STATUS_CHOICES, required=False, initial='', label='Status')
    serial = forms.CharField(max_length=50, required=False, label='Serial Number')

    class Meta:
        nullable_fields = ['tenant', 'platform']


class DeviceFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = Device
    q = forms.CharField(required=False, label='Search')
    site = FilterChoiceField(
        queryset=Site.objects.annotate(filter_count=Count('devices')),
        to_field_name='slug',
    )
    rack_group_id = FilterChoiceField(
        queryset=RackGroup.objects.select_related('site').annotate(filter_count=Count('racks__devices')),
        label='Rack group',
    )
    role = FilterChoiceField(
        queryset=DeviceRole.objects.annotate(filter_count=Count('devices')),
        to_field_name='slug',
    )
    tenant = FilterChoiceField(
        queryset=Tenant.objects.annotate(filter_count=Count('devices')), to_field_name='slug',
        null_option=(0, 'None'),
    )
    manufacturer_id = FilterChoiceField(
        queryset=Manufacturer.objects.all(),
        label='Manufacturer',
    )
    device_type_id = FilterChoiceField(
        queryset=DeviceType.objects.select_related('manufacturer').order_by('model').annotate(
            filter_count=Count('instances'),
        ),
        label='Model',
    )
    platform = FilterChoiceField(
        queryset=Platform.objects.annotate(filter_count=Count('devices')),
        to_field_name='slug',
        null_option=(0, 'None'),
    )
    status = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=FORM_STATUS_CHOICES),
    )
    mac_address = forms.CharField(
        required=False,
        label='MAC address',
    )


#
# Bulk device component creation
#

class DeviceBulkAddComponentForm(BootstrapMixin, forms.Form):
    pk = forms.ModelMultipleChoiceField(queryset=Device.objects.all(), widget=forms.MultipleHiddenInput)
    name_pattern = ExpandableNameField(label='Name')


class DeviceBulkAddInterfaceForm(forms.ModelForm, DeviceBulkAddComponentForm):

    class Meta:
        model = Interface
        fields = ['pk', 'name_pattern', 'form_factor', 'mgmt_only', 'description']


#
# Console ports
#

class ConsolePortForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = ConsolePort
        fields = ['device', 'name']
        widgets = {
            'device': forms.HiddenInput(),
        }


class ConsolePortCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class ConsoleConnectionCSVForm(forms.Form):
    console_server = FlexibleModelChoiceField(
        queryset=Device.objects.filter(device_type__is_console_server=True),
        to_field_name='name',
        error_messages={
            'invalid_choice': 'Console server not found',
        }
    )
    cs_port = forms.CharField()
    device = FlexibleModelChoiceField(queryset=Device.objects.all(), to_field_name='name',
                                      error_messages={'invalid_choice': 'Device not found'})
    console_port = forms.CharField()
    status = forms.CharField(validators=[validate_connection_status])

    def clean(self):

        # Validate console server port
        if self.cleaned_data.get('console_server'):
            try:
                cs_port = ConsoleServerPort.objects.get(device=self.cleaned_data['console_server'],
                                                        name=self.cleaned_data['cs_port'])
                if ConsolePort.objects.filter(cs_port=cs_port):
                    raise forms.ValidationError("Console server port is already occupied (by {} {})"
                                                .format(cs_port.connected_console.device, cs_port.connected_console))
            except ConsoleServerPort.DoesNotExist:
                raise forms.ValidationError("Invalid console server port ({} {})"
                                            .format(self.cleaned_data['console_server'], self.cleaned_data['cs_port']))

        # Validate console port
        if self.cleaned_data.get('device'):
            try:
                console_port = ConsolePort.objects.get(device=self.cleaned_data['device'],
                                                       name=self.cleaned_data['console_port'])
                if console_port.cs_port:
                    raise forms.ValidationError("Console port is already connected (to {} {})"
                                                .format(console_port.cs_port.device, console_port.cs_port))
            except ConsolePort.DoesNotExist:
                raise forms.ValidationError("Invalid console port ({} {})"
                                            .format(self.cleaned_data['device'], self.cleaned_data['console_port']))


class ConsoleConnectionImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=ConsoleConnectionCSVForm)

    def clean(self):
        records = self.cleaned_data.get('csv')
        if not records:
            return

        connection_list = []

        for i, record in enumerate(records, start=1):
            form = self.fields['csv'].csv_form(data=record)
            if form.is_valid():
                console_port = ConsolePort.objects.get(device=form.cleaned_data['device'],
                                                       name=form.cleaned_data['console_port'])
                console_port.cs_port = ConsoleServerPort.objects.get(device=form.cleaned_data['console_server'],
                                                                     name=form.cleaned_data['cs_port'])
                if form.cleaned_data['status'] == 'planned':
                    console_port.connection_status = CONNECTION_STATUS_PLANNED
                else:
                    console_port.connection_status = CONNECTION_STATUS_CONNECTED
                connection_list.append(console_port)
            else:
                for field, errors in form.errors.items():
                    for e in errors:
                        self.add_error('csv', "Record {} {}: {}".format(i, field, e))

        self.cleaned_data['csv'] = connection_list


class ConsolePortConnectionForm(BootstrapMixin, forms.ModelForm):
    site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        widget=forms.HiddenInput(),
    )
    rack = forms.ModelChoiceField(
        queryset=Rack.objects.all(),
        label='Rack',
        required=False,
        widget=forms.Select(
            attrs={'filter-for': 'console_server', 'nullable': 'true'}
        )
    )
    console_server = forms.ModelChoiceField(
        queryset=Device.objects.all(),
        label='Console Server',
        required=False,
        widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{site}}&rack_id={{rack}}&is_console_server=True',
            display_field='display_name',
            attrs={'filter-for': 'cs_port'}
        )
    )
    livesearch = forms.CharField(
        required=False,
        label='Console Server',
        widget=Livesearch(
            query_key='q',
            query_url='dcim-api:device_list',
            field_to_update='console_server',
        )
    )
    cs_port = forms.ModelChoiceField(
        queryset=ConsoleServerPort.objects.all(),
        label='Port',
        widget=APISelect(
            api_url='/api/dcim/devices/{{console_server}}/console-server-ports/',
            disabled_indicator='connected_console',
        )
    )

    class Meta:
        model = ConsolePort
        fields = ['site', 'rack', 'console_server', 'livesearch', 'cs_port', 'connection_status']
        labels = {
            'cs_port': 'Port',
            'connection_status': 'Status',
        }

    def __init__(self, *args, **kwargs):

        super(ConsolePortConnectionForm, self).__init__(*args, **kwargs)

        if not self.instance.pk:
            raise RuntimeError("ConsolePortConnectionForm must be initialized with an existing ConsolePort instance.")

        # Initialize rack choices if site is set
        if self.initial.get('site'):
            self.fields['rack'].queryset = Rack.objects.filter(site=self.initial['site'])
        else:
            self.fields['rack'].choices = []

        # Initialize console_server choices if rack or site is set
        if self.initial.get('rack'):
            self.fields['console_server'].queryset = Device.objects.filter(
                rack=self.initial['rack'], device_type__is_console_server=True
            )
        elif self.initial.get('site'):
            self.fields['console_server'].queryset = Device.objects.filter(
                site=self.initial['site'], rack__isnull=True, device_type__is_console_server=True
            )
        else:
            self.fields['console_server'].choices = []

        # Initialize CS port choices if console_server is set
        if self.initial.get('console_server'):
            self.fields['cs_port'].queryset = ConsoleServerPort.objects.filter(
                device=self.initial['console_server']
            )
        else:
            self.fields['cs_port'].choices = []


#
# Console server ports
#

class ConsoleServerPortForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = ConsoleServerPort
        fields = ['device', 'name']
        widgets = {
            'device': forms.HiddenInput(),
        }


class ConsoleServerPortCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class ConsoleServerPortConnectionForm(BootstrapMixin, forms.Form):
    site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        widget=forms.HiddenInput(),
    )
    rack = forms.ModelChoiceField(
        queryset=Rack.objects.all(),
        label='Rack',
        required=False,
        widget=forms.Select(
            attrs={'filter-for': 'device', 'nullable': 'true'}
        )
    )
    device = forms.ModelChoiceField(
        queryset=Device.objects.all(),
        label='Device',
        required=False,
        widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{site}}&rack_id={{rack}}',
            display_field='display_name',
            attrs={'filter-for': 'port'}
        )
    )
    livesearch = forms.CharField(
        required=False,
        label='Device',
        widget=Livesearch(
            query_key='q',
            query_url='dcim-api:device_list',
            field_to_update='device'
        )
    )
    port = forms.ModelChoiceField(
        queryset=ConsolePort.objects.all(),
        label='Port',
        widget=APISelect(
            api_url='/api/dcim/devices/{{device}}/console-ports/',
            disabled_indicator='cs_port'
        )
    )
    connection_status = forms.BooleanField(
        required=False,
        initial=CONNECTION_STATUS_CONNECTED,
        label='Status',
        widget=forms.Select(
            choices=CONNECTION_STATUS_CHOICES
        )
    )

    class Meta:
        fields = ['site', 'rack', 'device', 'livesearch', 'port', 'connection_status']
        labels = {
            'connection_status': 'Status',
        }

    def __init__(self, *args, **kwargs):

        super(ConsoleServerPortConnectionForm, self).__init__(*args, **kwargs)

        # Initialize rack choices if site is set
        if self.initial.get('site'):
            self.fields['rack'].queryset = Rack.objects.filter(site=self.initial['site'])
        else:
            self.fields['rack'].choices = []

        # Initialize device choices if rack or site is set
        if self.initial.get('rack'):
            self.fields['device'].queryset = Device.objects.filter(rack=self.initial['rack'])
        elif self.initial.get('site'):
            self.fields['device'].queryset = Device.objects.filter(site=self.initial['site'], rack__isnull=True)
        else:
            self.fields['device'].choices = []

        # Initialize port choices if device is set
        if self.initial.get('device'):
            self.fields['port'].queryset = ConsolePort.objects.filter(device=self.initial['device'])
        else:
            self.fields['port'].choices = []


#
# Power ports
#

class PowerPortForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = PowerPort
        fields = ['device', 'name']
        widgets = {
            'device': forms.HiddenInput(),
        }


class PowerPortCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class PowerConnectionCSVForm(forms.Form):
    pdu = FlexibleModelChoiceField(
        queryset=Device.objects.filter(device_type__is_pdu=True),
        to_field_name='name',
        error_messages={
            'invalid_choice': 'PDU not found.',
        }
    )
    power_outlet = forms.CharField()
    device = FlexibleModelChoiceField(queryset=Device.objects.all(), to_field_name='name',
                                      error_messages={'invalid_choice': 'Device not found'})
    power_port = forms.CharField()
    status = forms.CharField(validators=[validate_connection_status])

    def clean(self):

        # Validate power outlet
        if self.cleaned_data.get('pdu'):
            try:
                power_outlet = PowerOutlet.objects.get(device=self.cleaned_data['pdu'],
                                                       name=self.cleaned_data['power_outlet'])
                if PowerPort.objects.filter(power_outlet=power_outlet):
                    raise forms.ValidationError("Power outlet is already occupied (by {} {})"
                                                .format(power_outlet.connected_port.device,
                                                        power_outlet.connected_port))
            except PowerOutlet.DoesNotExist:
                raise forms.ValidationError("Invalid PDU port ({} {})"
                                            .format(self.cleaned_data['pdu'], self.cleaned_data['power_outlet']))

        # Validate power port
        if self.cleaned_data.get('device'):
            try:
                power_port = PowerPort.objects.get(device=self.cleaned_data['device'],
                                                   name=self.cleaned_data['power_port'])
                if power_port.power_outlet:
                    raise forms.ValidationError("Power port is already connected (to {} {})"
                                                .format(power_port.power_outlet.device, power_port.power_outlet))
            except PowerPort.DoesNotExist:
                raise forms.ValidationError("Invalid power port ({} {})"
                                            .format(self.cleaned_data['device'], self.cleaned_data['power_port']))


class PowerConnectionImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=PowerConnectionCSVForm)

    def clean(self):
        records = self.cleaned_data.get('csv')
        if not records:
            return

        connection_list = []

        for i, record in enumerate(records, start=1):
            form = self.fields['csv'].csv_form(data=record)
            if form.is_valid():
                power_port = PowerPort.objects.get(device=form.cleaned_data['device'],
                                                   name=form.cleaned_data['power_port'])
                power_port.power_outlet = PowerOutlet.objects.get(device=form.cleaned_data['pdu'],
                                                                  name=form.cleaned_data['power_outlet'])
                if form.cleaned_data['status'] == 'planned':
                    power_port.connection_status = CONNECTION_STATUS_PLANNED
                else:
                    power_port.connection_status = CONNECTION_STATUS_CONNECTED
                connection_list.append(power_port)
            else:
                for field, errors in form.errors.items():
                    for e in errors:
                        self.add_error('csv', "Record {} {}: {}".format(i, field, e))

        self.cleaned_data['csv'] = connection_list


class PowerPortConnectionForm(BootstrapMixin, forms.ModelForm):
    site = forms.ModelChoiceField(queryset=Site.objects.all(), widget=forms.HiddenInput())
    rack = forms.ModelChoiceField(
        queryset=Rack.objects.all(),
        label='Rack',
        required=False,
        widget=forms.Select(
            attrs={'filter-for': 'pdu', 'nullable': 'true'}
        )
    )
    pdu = forms.ModelChoiceField(
        queryset=Device.objects.all(),
        label='PDU',
        required=False,
        widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{site}}&rack_id={{rack}}&is_pdu=True',
            display_field='display_name',
            attrs={'filter-for': 'power_outlet'}
        )
    )
    livesearch = forms.CharField(
        required=False,
        label='PDU',
        widget=Livesearch(
            query_key='q',
            query_url='dcim-api:device_list',
            field_to_update='pdu'
        )
    )
    power_outlet = forms.ModelChoiceField(
        queryset=PowerOutlet.objects.all(),
        label='Outlet',
        widget=APISelect(
            api_url='/api/dcim/devices/{{pdu}}/power-outlets/',
            disabled_indicator='connected_port'
        )
    )

    class Meta:
        model = PowerPort
        fields = ['site', 'rack', 'pdu', 'livesearch', 'power_outlet', 'connection_status']
        labels = {
            'power_outlet': 'Outlet',
            'connection_status': 'Status',
        }

    def __init__(self, *args, **kwargs):

        super(PowerPortConnectionForm, self).__init__(*args, **kwargs)

        if not self.instance.pk:
            raise RuntimeError("PowerPortConnectionForm must be initialized with an existing PowerPort instance.")

        # Initialize rack choices if site is set
        if self.initial.get('site'):
            self.fields['rack'].queryset = Rack.objects.filter(site=self.initial['site'])
        else:
            self.fields['rack'].choices = []

        # Initialize pdu choices if rack or site is set
        if self.initial.get('rack'):
            self.fields['pdu'].queryset = Device.objects.filter(
                rack=self.initial['rack'], device_type__is_pdu=True
            )
        elif self.initial.get('site'):
            self.fields['pdu'].queryset = Device.objects.filter(
                site=self.initial['site'], rack__isnull=True, device_type__is_pdu=True
            )
        else:
            self.fields['pdu'].choices = []

        # Initialize power outlet choices if pdu is set
        if self.initial.get('pdu'):
            self.fields['power_outlet'].queryset = PowerOutlet.objects.filter(device=self.initial['pdu'])
        else:
            self.fields['power_outlet'].choices = []


#
# Power outlets
#

class PowerOutletForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = PowerOutlet
        fields = ['device', 'name']
        widgets = {
            'device': forms.HiddenInput(),
        }


class PowerOutletCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class PowerOutletConnectionForm(BootstrapMixin, forms.Form):
    site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        widget=forms.HiddenInput()
    )
    rack = forms.ModelChoiceField(
        queryset=Rack.objects.all(),
        label='Rack',
        required=False,
        widget=forms.Select(
            attrs={'filter-for': 'device', 'nullable': 'true'}
        )
    )
    device = forms.ModelChoiceField(
        queryset=Device.objects.all(),
        label='Device',
        required=False,
        widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{site}}&rack_id={{rack}}',
            display_field='display_name',
            attrs={'filter-for': 'port'}
        )
    )
    livesearch = forms.CharField(
        required=False,
        label='Device',
        widget=Livesearch(
            query_key='q',
            query_url='dcim-api:device_list',
            field_to_update='device'
        )
    )
    port = forms.ModelChoiceField(
        queryset=PowerPort.objects.all(),
        label='Port',
        widget=APISelect(
            api_url='/api/dcim/devices/{{device}}/power-ports/',
            disabled_indicator='power_outlet'
        )
    )
    connection_status = forms.BooleanField(
        required=False,
        initial=CONNECTION_STATUS_CONNECTED,
        label='Status',
        widget=forms.Select(
            choices=CONNECTION_STATUS_CHOICES
        )
    )

    class Meta:
        fields = ['site', 'rack', 'device', 'livesearch', 'port', 'connection_status']
        labels = {
            'connection_status': 'Status',
        }

    def __init__(self, *args, **kwargs):

        super(PowerOutletConnectionForm, self).__init__(*args, **kwargs)

        # Initialize rack choices if site is set
        if self.initial.get('site'):
            self.fields['rack'].queryset = Rack.objects.filter(site=self.initial['site'])
        else:
            self.fields['rack'].choices = []

        # Initialize device choices if rack or site is set
        if self.initial.get('rack'):
            self.fields['device'].queryset = Device.objects.filter(rack=self.initial['rack'])
        elif self.initial.get('site'):
            self.fields['device'].queryset = Device.objects.filter(site=self.initial['site'], rack__isnull=True)
        else:
            self.fields['device'].choices = []

        # Initialize port choices if device is set
        if self.initial.get('device'):
            self.fields['port'].queryset = PowerPort.objects.filter(device=self.initial['device'])
        else:
            self.fields['port'].choices = []


#
# Interfaces
#

class InterfaceForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = Interface
        fields = ['device', 'name', 'form_factor', 'lag', 'mac_address', 'mgmt_only', 'description']
        widgets = {
            'device': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(InterfaceForm, self).__init__(*args, **kwargs)

        # Limit LAG choices to interfaces belonging to this device
        if self.is_bound:
            self.fields['lag'].queryset = Interface.objects.order_naturally().filter(
                device_id=self.data['device'], form_factor=IFACE_FF_LAG
            )
        else:
            self.fields['lag'].queryset = Interface.objects.order_naturally().filter(
                device=self.instance.device, form_factor=IFACE_FF_LAG
            )


class InterfaceCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')
    form_factor = forms.ChoiceField(choices=IFACE_FF_CHOICES)
    lag = forms.ModelChoiceField(queryset=Interface.objects.all(), required=False, label='Parent LAG')
    mac_address = MACAddressFormField(required=False, label='MAC Address')
    mgmt_only = forms.BooleanField(required=False, label='OOB Management')
    description = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, **kwargs):
        super(InterfaceCreateForm, self).__init__(*args, **kwargs)

        # Limit LAG choices to interfaces belonging to this device
        if self.device is not None:
            self.fields['lag'].queryset = Interface.objects.order_naturally().filter(
                device=self.device, form_factor=IFACE_FF_LAG
            )
        else:
            self.fields['lag'].queryset = Interface.objects.none()


class InterfaceBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=Interface.objects.all(), widget=forms.MultipleHiddenInput)
    device = forms.ModelChoiceField(queryset=Device.objects.all(), widget=forms.HiddenInput)
    lag = forms.ModelChoiceField(queryset=Interface.objects.all(), required=False, label='Parent LAG')
    form_factor = forms.ChoiceField(choices=add_blank_choice(IFACE_FF_CHOICES), required=False)
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['lag', 'description']

    def __init__(self, *args, **kwargs):
        super(InterfaceBulkEditForm, self).__init__(*args, **kwargs)

        # Limit LAG choices to interfaces which belong to the parent device.
        device = None
        if self.initial.get('device'):
            try:
                device = Device.objects.get(pk=self.initial.get('device'))
            except Device.DoesNotExist:
                pass
        if device is not None:
            interface_ordering = device.device_type.interface_ordering
            self.fields['lag'].queryset = Interface.objects.order_naturally(method=interface_ordering).filter(
                device=device, form_factor=IFACE_FF_LAG
            )
        else:
            self.fields['lag'].choices = []


#
# Interface connections
#

class InterfaceConnectionForm(BootstrapMixin, forms.ModelForm):
    interface_a = forms.ChoiceField(
        choices=[],
        widget=SelectWithDisabled,
        label='Interface'
    )
    site_b = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        label='Site',
        required=False,
        widget=forms.Select(
            attrs={'filter-for': 'rack_b'}
        )
    )
    rack_b = forms.ModelChoiceField(
        queryset=Rack.objects.all(),
        label='Rack',
        required=False,
        widget=APISelect(
            api_url='/api/dcim/racks/?site_id={{site_b}}',
            attrs={'filter-for': 'device_b', 'nullable': 'true'}
        )
    )
    device_b = forms.ModelChoiceField(
        queryset=Device.objects.all(),
        label='Device',
        required=False,
        widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{site_b}}&rack_id={{rack_b}}',
            display_field='display_name',
            attrs={'filter-for': 'interface_b'}
        )
    )
    livesearch = forms.CharField(
        required=False,
        label='Device',
        widget=Livesearch(
            query_key='q',
            query_url='dcim-api:device_list',
            field_to_update='device_b'
        )
    )
    interface_b = forms.ModelChoiceField(
        queryset=Interface.objects.all(),
        label='Interface',
        widget=APISelect(
            api_url='/api/dcim/devices/{{device_b}}/interfaces/?type=physical',
            disabled_indicator='is_connected'
        )
    )

    class Meta:
        model = InterfaceConnection
        fields = ['interface_a', 'site_b', 'rack_b', 'device_b', 'interface_b', 'livesearch', 'connection_status']

    def __init__(self, device_a, *args, **kwargs):

        super(InterfaceConnectionForm, self).__init__(*args, **kwargs)

        # Initialize interface A choices
        device_a_interfaces = Interface.objects.order_naturally().filter(device=device_a).exclude(
            form_factor__in=VIRTUAL_IFACE_TYPES
        ).select_related(
            'circuit_termination', 'connected_as_a', 'connected_as_b'
        )
        self.fields['interface_a'].choices = [
            (iface.id, {'label': iface.name, 'disabled': iface.is_connected}) for iface in device_a_interfaces
        ]

        # Initialize rack_b choices if site_b is set
        if self.initial.get('site_b'):
            self.fields['rack_b'].queryset = Rack.objects.filter(site=self.initial['site_b'])
        else:
            self.fields['rack_b'].choices = []

        # Initialize device_b choices if rack_b or site_b is set
        if self.initial.get('rack_b'):
            self.fields['device_b'].queryset = Device.objects.filter(rack=self.initial['rack_b'])
        elif self.initial.get('site_b'):
            self.fields['device_b'].queryset = Device.objects.filter(site=self.initial['site_b'], rack__isnull=True)
        else:
            self.fields['device_b'].choices = []

        # Initialize interface_b choices if device_b is set
        if self.initial.get('device_b'):
            device_b_interfaces = Interface.objects.filter(device=self.initial['device_b']).exclude(
                form_factor__in=VIRTUAL_IFACE_TYPES
            ).select_related(
                'circuit_termination', 'connected_as_a', 'connected_as_b'
            )
        else:
            device_b_interfaces = []
        self.fields['interface_b'].choices = [
            (iface.id, {'label': iface.name, 'disabled': iface.is_connected}) for iface in device_b_interfaces
        ]


class InterfaceConnectionCSVForm(forms.Form):
    device_a = FlexibleModelChoiceField(
        queryset=Device.objects.all(),
        to_field_name='name',
        error_messages={'invalid_choice': 'Device A not found.'}
    )
    interface_a = forms.CharField()
    device_b = FlexibleModelChoiceField(
        queryset=Device.objects.all(),
        to_field_name='name',
        error_messages={'invalid_choice': 'Device B not found.'}
    )
    interface_b = forms.CharField()
    status = forms.CharField(
        validators=[validate_connection_status]
    )

    def clean(self):

        # Validate interface A
        if self.cleaned_data.get('device_a'):
            try:
                interface_a = Interface.objects.get(device=self.cleaned_data['device_a'],
                                                    name=self.cleaned_data['interface_a'])
            except Interface.DoesNotExist:
                raise forms.ValidationError("Invalid interface ({} {})"
                                            .format(self.cleaned_data['device_a'], self.cleaned_data['interface_a']))
            try:
                InterfaceConnection.objects.get(Q(interface_a=interface_a) | Q(interface_b=interface_a))
                raise forms.ValidationError("{} {} is already connected"
                                            .format(self.cleaned_data['device_a'], self.cleaned_data['interface_a']))
            except InterfaceConnection.DoesNotExist:
                pass

        # Validate interface B
        if self.cleaned_data.get('device_b'):
            try:
                interface_b = Interface.objects.get(device=self.cleaned_data['device_b'],
                                                    name=self.cleaned_data['interface_b'])
            except Interface.DoesNotExist:
                raise forms.ValidationError("Invalid interface ({} {})"
                                            .format(self.cleaned_data['device_b'], self.cleaned_data['interface_b']))
            try:
                InterfaceConnection.objects.get(Q(interface_a=interface_b) | Q(interface_b=interface_b))
                raise forms.ValidationError("{} {} is already connected"
                                            .format(self.cleaned_data['device_b'], self.cleaned_data['interface_b']))
            except InterfaceConnection.DoesNotExist:
                pass


class InterfaceConnectionImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=InterfaceConnectionCSVForm)

    def clean(self):
        records = self.cleaned_data.get('csv')
        if not records:
            return

        connection_list = []
        occupied_interfaces = []

        for i, record in enumerate(records, start=1):
            form = self.fields['csv'].csv_form(data=record)
            if form.is_valid():
                interface_a = Interface.objects.get(device=form.cleaned_data['device_a'],
                                                    name=form.cleaned_data['interface_a'])
                if interface_a in occupied_interfaces:
                    raise forms.ValidationError("{} {} found in multiple connections"
                                                .format(interface_a.device.name, interface_a.name))
                interface_b = Interface.objects.get(device=form.cleaned_data['device_b'],
                                                    name=form.cleaned_data['interface_b'])
                if interface_b in occupied_interfaces:
                    raise forms.ValidationError("{} {} found in multiple connections"
                                                .format(interface_b.device.name, interface_b.name))
                connection = InterfaceConnection(interface_a=interface_a, interface_b=interface_b)
                if form.cleaned_data['status'] == 'planned':
                    connection.connection_status = CONNECTION_STATUS_PLANNED
                else:
                    connection.connection_status = CONNECTION_STATUS_CONNECTED
                connection_list.append(connection)
                occupied_interfaces.append(interface_a)
                occupied_interfaces.append(interface_b)
            else:
                for field, errors in form.errors.items():
                    for e in errors:
                        self.add_error('csv', "Record {} {}: {}".format(i, field, e))

        self.cleaned_data['csv'] = connection_list


class InterfaceConnectionDeletionForm(BootstrapMixin, forms.Form):
    confirm = forms.BooleanField(required=True)
    # Used for HTTP redirect upon successful deletion
    device = forms.ModelChoiceField(queryset=Device.objects.all(), widget=forms.HiddenInput(), required=False)


#
# Device bays
#

class DeviceBayForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = DeviceBay
        fields = ['device', 'name']
        widgets = {
            'device': forms.HiddenInput(),
        }


class DeviceBayCreateForm(DeviceComponentForm):
    name_pattern = ExpandableNameField(label='Name')


class PopulateDeviceBayForm(BootstrapMixin, forms.Form):
    installed_device = forms.ModelChoiceField(
        queryset=Device.objects.all(),
        label='Child Device',
        help_text="Child devices must first be created and assigned to the site/rack of the parent device."
    )

    def __init__(self, device_bay, *args, **kwargs):

        super(PopulateDeviceBayForm, self).__init__(*args, **kwargs)

        self.fields['installed_device'].queryset = Device.objects.filter(
            site=device_bay.device.site,
            rack=device_bay.device.rack,
            parent_bay__isnull=True,
            device_type__u_height=0,
            device_type__subdevice_role=SUBDEVICE_ROLE_CHILD
        ).exclude(pk=device_bay.device.pk)


#
# Connections
#

class ConsoleConnectionFilterForm(BootstrapMixin, forms.Form):
    site = forms.ModelChoiceField(required=False, queryset=Site.objects.all(), to_field_name='slug')
    device = forms.CharField(required=False, label='Device name')


class PowerConnectionFilterForm(BootstrapMixin, forms.Form):
    site = forms.ModelChoiceField(required=False, queryset=Site.objects.all(), to_field_name='slug')
    device = forms.CharField(required=False, label='Device name')


class InterfaceConnectionFilterForm(BootstrapMixin, forms.Form):
    site = forms.ModelChoiceField(required=False, queryset=Site.objects.all(), to_field_name='slug')
    device = forms.CharField(required=False, label='Device name')


#
# Modules
#

class ModuleForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = Module
        fields = ['name', 'manufacturer', 'part_id', 'serial']
