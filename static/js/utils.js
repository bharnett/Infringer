/**
 * Created by e440614 on 12/8/2014.
 */
//function ajaxer(url, data, beforeSend, errorCallback, successCallback) {
//    $.ajax({
//        url: url,
//        type: 'POST',
//        data: JSON.stringify(data),
//        dataType: 'text',
//        contentType: 'application/json',
//        error: errorCallback,
//        beforeSend: beforeSend,
//        success: function (data) {
//            var ar = $.parseJSON($.parseJSON(data));
//            $('#ajax-status').text(' ' + ar.message);
//            if (ar.status == 'success') {
//                $('#ajax-status strong').text('Success')
//                $('#ajax-status').addClass('alert-success').remove('alert-error');
//                $("#ajax-status").toggleClass('in')
//            }
//            else {
//                $('#ajax-status').addClass('alert-error').remove('alert-success');
//                $('#ajax-status strong').text('Error')
//                $("#ajax-status").toggleClass('in')
//                window.setTimeout(function () {
//                    $("#ajax-status").toggleClass('in')
//                }, 5000)
//                errorCallback;
//            }
//            successCallback(data);
//        }
//    })
//}
function showStatus(isError, message) {
    PNotify.prototype.options.styling = 'bootstrap3';
    new PNotify({
        title: isError ? 'Error' : 'Success',
        text: message,
        icon: true,
        type: isError ? 'error' : 'success'
    });
}