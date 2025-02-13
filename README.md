
<img src="https://github.com/user-attachments/assets/b30e2c38-dc19-49a5-973d-51e1dafe5c4d" width="100%" />

<br/>

Use the CLI to upload, manage, and query documents based on fine-tuned LLM models. It uses the smartloop API to manage projects and documents and gives you an easy way to quickly process contents and reason based on it.


![PyPI - Version](https://img.shields.io/pypi/v/smartloop)

## Requirements

- Python 3.11

## Installation

Install the CLI with the following command:

```
pip install -U smartloop

```
Once installed, check that everything is setup correctly:



```console
smartloop --help
                                                                                                                                                                     
 Usage: smartloop [OPTIONS] COMMAND [ARGS]...                                                                                                                          
                                                                                                                                                                     
╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                                                                                           │
│ --show-completion             Show completion for the current shell, to copy it or customize the installation.                                                    │
│ --help                        Show this message and exit.                                                                                                         │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ agent     Manage agent(s)                                                                                                                                         │
│ login     Authenticate using a token from https://api.smartloop.ai/v1/redoc                                                                                       │
│ run       Starts a chat session with a selected agent                                                                                                             │
│ upload    Upload document for the selected agent                                                                                                                  │
│ version   Version of the cli                                                                                                                                      │
│ whoami    Find out which account you are logged in                                                                                                                │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


```

## Setup
First you will need to create a free [account](https://agent.smartloop.ai/signup), verify and configure your account. 
Once verified, copy your [developer token](https://agent.smartloop.ai/developer) to the clipboard. If you have any problem setting up your account please reach out to us at `hello@smartloop.ai` and we should be able to get you started.

Once you have your token, run the following command in your terminal:

```bash
smartloop login
```

## Create an Agent

Once you have configured the CLI , you can start creating agent using the following command:

```bash
smartloop agent create --name microsoft
```

## Select an Agent

Use the following command to interactively select an agent:


```bash
smartloop agent select
```

## Upload Document

Once the agent is selected , upload documents from your folder or a specific file to personalized your agent, in this case I am uploading the a document describing Microsoft online services form my local machine:

```bash
smartloop upload --path=~/document1.pdf
```

## Run It

Execute the following command to start prompting:

```bash
smartloop run
```

This will bring up the interface to prompt your queries as shown below:

```bash
Microsoft(microsoft-24-07-2024)
======================================
Enter prompt (Ctrl-C to exit): 
what the SLA for azure open ai
⠋
The SLA (Service Level Agreement) for Azure OpenAI is not explicitly mentioned in the provided text. However, it's possible that the SLA for Azure OpenAI might be similar to the one mentioned below:

"Uptime Percentage"

* Service Credit:
+ < 99.9%: 10%
+ < 99%: 25%
+ < 95%: 100%

Please note that this is not a direct quote from the provided text, but rather an inference based on the format and structure of the SLA mentioned for other Azure services (e.g., SAP HANA on Azure High Availability Pair). To confirm the actual SLA for Azure OpenAI, you should check the official Microsoft documentation or contact their support team.

Prompt message (Ctrl-C to exit):
```

In order to set `temperature` of your conversation, which ranges from 0.0 to 1.0, use the following command:

```bash 
smartloop agent set --id=project_id --temp=0.3

```

To enable memory to retain context in the conversation, use the following command:

```bash 
smartloop agent set --id=project_id --memory

```

To disable memory, use the following command:

```bash 
smartloop agent set --id=project_id --no-memory

```

`LLM temperature is a parameter that influences the language model's output, determining whether the output is more random and creative or more predictable.`

The higher value tends towards more creative answer


## Supported Documents types

* PDF
* DOCX
* TXT
* CSV


## Contributing

Contributions are welcome! Please create a pull request with your changes. 


## Contact

If you have any questions or suggestions, please feel free to reach out to hello@smartloop.ai


## References

* [Smartloop API Documentation](https://api.smartloop.ai/v1/redoc)
* [Meta LLaMA](https://research.facebook.com/publications/llama-open-and-efficient-foundation-language-models/)
* [LoRA](https://arxiv.org/abs/2106.09685)



## License

This project is licensed under the terms of the MIT license.
