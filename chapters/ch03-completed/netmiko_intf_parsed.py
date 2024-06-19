from netmiko import ConnectHandler

device = ConnectHandler(
    host='ceos-01',
    username='netobs',
    password='netobs123',
    device_type='arista_eos'
)

show_run_output = device.send_command('show interface status', use_textfsm=True)

print(type(show_run_output))
print(show_run_output)
