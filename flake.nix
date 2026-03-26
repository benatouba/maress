{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv = {
      url = "github:cachix/devenv";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{ nixpkgs, devenv, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = devenv.lib.mkShell {
        inherit inputs pkgs;
        modules = [
          {
            devenv.root =
              let
                devenvRoot = builtins.getEnv "DEVENV_ROOT";
              in
              pkgs.lib.mkIf (devenvRoot != "") devenvRoot;
          }
          ./devenv.nix
        ];
      };
    };
}
