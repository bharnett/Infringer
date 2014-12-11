
function showStatus(isError, message) {
    PNotify.prototype.options.styling = 'bootstrap3';
    new PNotify({
        title: isError ? 'Error' : 'Success',
        text: message,
        icon: true,
        type: isError ? 'error' : 'success'
    });
}