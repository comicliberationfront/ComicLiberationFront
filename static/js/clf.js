$(document).ready(function(){
    $('a.download').click(function(){
        var seriesid = $(this).attr('data-seriesid')
        var comicid = $(this).attr('data-comicid')
        $.getJSON('/download/'+seriesid+'/'+comicid)
    })
 });

