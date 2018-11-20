# dyn-gandi
Use Gandi LiveDNS API to update DNS records with a dynamic IP.


#### Prequisites

- Go to your Gandi account security page: https://account.gandi.net/en/users/USER/security (where USER is your username)
- Generate your API key, to be copied into your configuration file
- Python 3.x


#### Installation

Download and unzip the sources :
```shell
$ curl --location https://github.com/Danamir/dyn-gandi/archive/master.zip --output dyn-gandi-master.zip
$ unzip dyn-gandi-master.zip
$ mv dyn-gandi-master/ dyn-gandi
$ cd dyn-gandi
```

_(Optional)_ Configure Python virtual environment :
```shell
$ python -m venv .env
$ . .env/bin/activate (Linux) 
-or-
$ .env/Script/activate.bat (Windows)
```

Install :
```shell
$ python setup.py develop
$ copy config.ini-dist config.ini
$ dyn_gandi --help
-or-
$ python dyn_gandi.py --help
```

Complete the `config.ini` file, in particular check the lines :
```ini
[api]
key =

[dns]
domain = 
records = @,www
```

#### Running
_Note: `dyn_gandi` can be substituted with `python dyn_gandi.py` if the former does'nt work._

Display help :
```shell
$ dyn_gandi --help
```

Dry run (without modifications) :
```shell
$ dyn_gandi --dry-run
```

Normal launch:
```shell
$ dyn_gandi
```

The log line will end by `[OK]` if no update was needed, `[UPDATE]` on successful update, and `[ERROR]` on error.
On success, the automatic backup snapshot is deleted ; on error the snapshot uuid is displayed in the log
for you to restore if needed.

#### Cron
Either create a scheduled task on windows, or add a crontab line. ie: 
```shell
$ crontab -e
* */2 * * * dyn_gandi --log /var/log/dyn-gandi.log
```

NB: If you used a Python virtual environment, replace the script by `<dyn-gandi-path>/.env/bin/dyn_gandi` .

##### Notes
  - [Gandi LiveDNS documentation](http://doc.livedns.gandi.net/)
  - Thanks [Gandyn](https://github.com/Chralu/gandyn) for the inspiration (and many years of use)
