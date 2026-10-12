"""Há quanto tempo o computador está sem teclado e mouse?

Pergunta ao próprio GNOME (serviço org.gnome.Mutter.IdleMonitor, o mesmo que
o Ubuntu usa para apagar a tela). Funciona em X11 e Wayland no GNOME.
Se o serviço não existir (outro ambiente gráfico), devolve None e o
navegador conta o tempo como antes.
"""

import time

from gi.repository import Gio, GLib

CONSULTAR_A_CADA = 5   # segundos: não precisa perguntar ao GNOME a todo instante


class MonitorDeInatividade:
    def __init__(self):
        self._proxy = None
        self._ultima_consulta = 0.0
        self._ultimo_valor = None
        try:
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES, None,
                "org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core",
                "org.gnome.Mutter.IdleMonitor", None)
        except GLib.Error:
            self._proxy = None

    def segundos_parado(self):
        """Segundos sem teclado/mouse, ou None se não der para saber."""
        if self._proxy is None:
            return None
        agora = time.monotonic()
        if agora - self._ultima_consulta >= CONSULTAR_A_CADA:
            self._ultima_consulta = agora
            try:
                resposta = self._proxy.call_sync("GetIdletime", None,
                                                 Gio.DBusCallFlags.NONE, 300, None)
                self._ultimo_valor = resposta.unpack()[0] / 1000
            except GLib.Error:
                self._proxy = None      # serviço sumiu: para de perguntar
                self._ultimo_valor = None
                return None
        else:
            # Entre consultas, soma o tempo passado (se estava parado, continua parado).
            if self._ultimo_valor is not None:
                return self._ultimo_valor + (agora - self._ultima_consulta)
        return self._ultimo_valor
