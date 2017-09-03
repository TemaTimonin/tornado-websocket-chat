window.onload = function(){
    InitChannelList()
    JoinChannel()
    var socket;
};

var InitChannelList = function(){
    var xhr = new XMLHttpRequest();
    xhr.open("GET", '/channel', true);
    xhr.onreadystatechange = function(){
    	var status;
		var data;
		var i = 0;
		if (xhr.readyState == 4) {
			status = xhr.status;
			if (status == 200) {
				data = JSON.parse(xhr.responseText);
				var channels_list = document.getElementById('channels-list');
				for (i; i < data.channels.length; i++){
				    channels_list.innerHTML += CreateChannelListElement(data.channels[i])
				}
				if (data.channels.length > 0){
				    ChangeChannel('list-channel-' + data.channels[0].id)
				}
			} else {
				alert('Something went wrong.');
			}
		}
    };
    xhr.send();
}

var CreateChannelListElement = function(channel){
    channel_id = 'channel-' + channel.id
    join_button = '<div class="pl-4 pt-1">' + channel.name + '</div>'
    delete_button = '<button class="btn" id="left-' + channel_id +
                    '" onclick="LeftChannel(event);event.cancelBubble=true;">X</button>'
    row  = '<div class="row justify-content-between">' + join_button + delete_button + '</div>'
    item_button = '<div class="list-group-item list-group-item-action" ' +
                'id="list-' + channel_id + '" onclick="ChangeChannelClick(event)">' + row + '</div>'
    return item_button
};

var ChangeChannel = function(channel_element_id){
    ActivateChannelListElement(channel_element_id)
    channel_id = GetChannelIdByElementId(channel_element_id)
    InitMessageHistory(channel_id)
    RegisterSockethandler(channel_id)
};

var ChangeChannelClick = function(event){
    channel_element_id = event.currentTarget.id
    ChangeChannel(channel_element_id)
};

var LeftChannel = function(event){
    var channel_element = event.currentTarget
    var channel_id = GetChannelIdByElementId(channel_element.id)
    var list_object = document.getElementById('list-channel-' + channel_id)
    var is_active = list_object.classList.contains('active')
    var xhr = new XMLHttpRequest();
    xhr.open("DELETE", '/channel/' + channel_id, true);
    xhr.onreadystatechange = function(){
    	var status;
		var data;
		var i = 0;
		if (xhr.readyState == 4) {
			status = xhr.status;
			if (status == 200) {
                var channels_list = document.getElementById('channels-list');
			    channels_list.removeChild(list_object)
                if (is_active === true) {
                    if (channels_list.childNodes.length > 0){
                        ChangeChannel(channels_list.childNodes[0].id)
                    }
                }
			} else {
				alert('Something went wrong.');
			}
		}
    };
    xhr.withCredentials = true;
    f_data = new FormData()
    f_data.set('_xsrf', getCookie('_xsrf'))
    xhr.send(f_data);
};

var ActivateChannelListElement = function(channel_element_id){
    var channels_list = document.getElementById('channels-list');
    Array.from(channels_list.childNodes).forEach(function(item, i, arr){
        if (item.id == channel_element_id){
            item.classList.add('active')
        }
        else {
            item.classList.remove('active')
        }
    });
}

var InitMessageHistory = function(channel_id){
    var message_area = document.getElementById('message-area')
    message_area.removeAttribute('hidden')
    var message_list = document.getElementById('message-list')
    message_list.innerHTML = ""

    var xhr = new XMLHttpRequest();
    xhr.open("GET", '/channel/' + channel_id, true);
    xhr.onreadystatechange = function(){
    	var status;
		var data;
		var i = 0;
		if (xhr.readyState == 4) {
			status = xhr.status;
			if (status == 200) {
				data = JSON.parse(xhr.responseText);
				var message_list = document.getElementById('message-list');
				for (i; i < data.messages.length; i++){
                    message_list.innerHTML += CreateMessage(data.messages[i])
				}
			} else {
				alert('Something went wrong.');
			}
		}
    };
    xhr.send();
}

var RegisterSockethandler = function(channel_id) {
    var socket_handler = new SocketHandler(channel_id);

    var form = document.getElementById('message-form');
    form.onsubmit = function(){
        socket_handler.send_message(form);
        return false;
    };
    form.onkeypress = function(e){
        if (e.keyCode == 13) {
            socket_handler.send_message(form);
            return false;
        }
    };
}

var SocketHandler = function(channel_id) {
    var url = "ws://" + location.host + "/chatsocket/" + channel_id;
    if (window.socket){
        window.socket.close()
    }
    window.socket = new WebSocket(url);
    window.socket.onmessage = function(event){
        var message = JSON.parse(event.data);
        var message_list = document.getElementById('message-list');
        message_list.innerHTML += CreateMessage(message)
        message_list.scrollTop = message_list.scrollHeight;
    };

    window.socket.onclose = function(event){
    };

    this.send_message = function(form){
        var elements = form.elements;
        var data = {};
        var i = 0;
        for (i; i < elements.length; i++){
            data[elements[i].name] = elements[i].value;
        }
        window.socket.send(JSON.stringify(data));
        var input = form.querySelector("input[type=text]");
        input.value = null;
        input.select();
    };
};


var CreateMessage = function(message){
    var datetime = timeConverter(message.timestamp)
    if (message.user != null){
        content = '<p class="">[' + datetime + '] ' + message.user + ': ' + message.text + '</p>'
    }
    else {
        content = '<p class="font-weight-bold">' + datetime + ' - ' + message.text + '</p>'
    }
    return '<div class="card-block border rounded text-wrap p-2 my-1" id="message-'
            + message.id + '">' + content + '</div>';
}

var GetChannelIdByElementId = function(element_id){
    return element_id.split('-')[2]
}


window.onbeforeunload = function(e){
    if (window.socket){
        window.socket.close()
    }
    return
}


var JoinChannel = function() {
    var form = document.getElementById('channel-join-form');
    form.onsubmit = function(){
        JoinChannelHandler(form)
        return false;
    };
    form.onkeypress = function(e){
        if (e.keyCode == 13) {
            JoinChannelHandler(form);
            return false;
        }
    };
}

var JoinChannelHandler = function(form) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", '/channel', true);
    xhr.onreadystatechange = function(){
    	var status;
		var data;
		var i = 0;
		if (xhr.readyState == 4) {
			status = xhr.status;
			if (status == 200) {
				data = JSON.parse(xhr.responseText);
				var channels_list = document.getElementById('channels-list');
				if (data.channel.already_joined === false){
				    channels_list.innerHTML += CreateChannelListElement(data.channel);
				}
				ChangeChannel('list-channel-' + data.channel.id)
				var input = form.querySelector("input[type=text]");
                input.value = null;
			} else {
				alert('Something went wrong.');
			}
		}
    };
        xhr.send(new FormData(form));
};


function getCookie(name) {
  var matches = document.cookie.match(new RegExp(
    "(?:^|; )" + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + "=([^;]*)"
  ));
  return matches ? decodeURIComponent(matches[1]) : undefined;
}


function timeConverter(timestamp){
    var a = new Date(timestamp * 1000);
    var year = a.getFullYear();
    var month = a.getMonth() + 1;
    var date = a.getDate();
    var hour = a.getHours();
    var min = a.getMinutes();
    var sec = a.getSeconds();
    if(date < 10){
        date = '0' + date;
    }
    if(month < 10){
        month = '0' + month;
    }
    if(hour < 10){
        hour = '0' + hour;
    }
    if(min < 10){
        min = '0' + min;
    }
    if(sec < 10){
        sec = '0' + sec;
    }

    var time = date + '.' + month + '.' + year + ' ' + hour + ':' + min + ':' + sec ;
    return time;
}

