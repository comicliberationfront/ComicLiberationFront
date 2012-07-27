
var downloadUpdateTimer = false
function updateDownloads() {
    console.log('Fetching downloads progress...')
    $.getJSON('/downloads', function(data){
        var progressList = $('.download-progress')
        progressList.empty()

        var downloadCount = 0
        $.each(data, function(key, val){
            ++downloadCount
            progressList.append('<div>' +
                '<p>' + val['title'] + '</p>' +
                '<div id="download-' + key + '"></div>' +
                '</div>')
            $('#download-' + key, progressList).progressbar({ value: val['progress'] })
        })
        
        var container = $('#downloads')
        if (downloadCount == 0) {
            clearInterval(downloadUpdateTimer)
            downloadUpdateTimer = false
            if (!container.is(':hidden')) {
                container.hide('slide', { direction: 'down' }, 500)
            }
            return
        } else if (container.is(":hidden")) {
            container.show('slide', { direction: 'up' }, 500)
        }
    })
}

$(document).ready(function(){
    if (downloadUpdateTimer === false) {
        downloadUpdateTimer = setInterval(updateDownloads, 1000)
    }

    $('a.download').click(function(){
        var seriesid = $(this).attr('data-seriesid')
        var comicid = $(this).attr('data-comicid')
        $.getJSON('/download/'+seriesid+'/'+comicid)
        if (downloadUpdateTimer === false) {
            downloadUpdateTimer = setInterval(updateDownloads, 1000)
        }
    })
 });

