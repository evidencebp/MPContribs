import 'bootstrap';
import 'bootstrap-tokenfield';
import 'jquery-form';
import 'jquery-validation';
import 'czmore';

$('#authors').tokenfield({});

function prepareRequest(formData, jqForm, options) {
    $('.alert-success').hide(); $('.alert-danger').hide();
    var start = 5;
    var nrefs = parseInt(formData.splice(start, 1)[0]['value']);
    if (nrefs < 1) {
        $('.alert-danger').html('Please add references.').show();
        return false;
    }
    var urls = {name: 'urls', value: {}};
    for (var i = 0; i < nrefs; i++) {
        var key_url = formData.splice(start+i, 2);
        urls['value'][key_url[0]['value']] = key_url[1]['value'];
    }
    formData.push(urls);
    return true;
}

function processJson(data) { // 'data' is the json object returned from the server
    // TODO success message not showing
    $('.alert-success').hide(); $('.alert-danger').hide();
    if (data.status === 200) {
        $('.alert-success').html('<span class="glyphicon glyphicon-ok" aria-hidden="true"></span>').show();
    } else {
        $('.alert-danger').html(data.responseText).show();
    }
    console.log(data.responseJSON);
}

$.validator.addMethod("alphanumeric", function(value, element) {
    return this.optional(element) || /^[\w_]+$/i.test(value);
}, "Please use letters, numbers, and underscores only.");

$('#apply-form').validate({
    rules: {
        project: {alphanumeric: true},
        url_1: {url: true, required: true},
        url_2: {url: true},
        url_3: {url: true},
        url_4: {url: true},
        url_5: {url: true}
    },
    highlight: function (element) {
        $(element).nextAll('.glyphicon').removeClass('glyphicon-ok').addClass('glyphicon-remove');
        $(element).closest('.form-group').removeClass('has-success').addClass('has-error');
    },
    unhighlight: function (element) {
        $(element).nextAll('.glyphicon').removeClass('glyphicon-remove').addClass('glyphicon-ok');
        $(element).closest('.form-group').removeClass('has-error').addClass('has-success');
    },
    errorElement: 'span', errorClass: 'help-block',
    errorPlacement: function(error, element) {
        if(element.parent('.input-group').length) {
            error.insertAfter(element.parent());
        } else { error.insertAfter(element); }
    },
    submitHandler: function(form) { $(form).ajaxSubmit({
        beforeSubmit: prepareRequest, success: processJson, error: processJson,
        url: window.api['host'] + 'projects/',
        type: 'POST', dataType: 'json', requestFormat: 'json'
    }); }
});

$("#czContainer").czMore({
    max: 5, styleOverride: true,
    onAdd: function(index) {
        $('.btnMinus').addClass('col-sm-1').html('<span class="glyphicon glyphicon-remove" aria-hidden="true"></span>');
    }
});
$('.btnPlus').html('<span class="glyphicon glyphicon-plus" style="top: 10px;" aria-hidden="true"></span>')
